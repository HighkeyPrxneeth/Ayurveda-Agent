"""
Hierarchical Clinical Council - The Supervisor

This is the main orchestration layer that replaces the PER workflow.
The Supervisor (Clinical Director) manages state and routes to specialists.

Architecture:
1. SemanticRouter performs zero-shot classification (<200ms)
2. Simple queries → FastResponder (Llama-3-8B)
3. Complex queries → Supervisor → Specialist Workers
4. All outputs pass through IronDome Guardrails

The Supervisor does NOT solve problems. It tracks state and delegates.
"""

from typing import TypedDict, Literal, Optional, Annotated, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass
import logging
import asyncio

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..config import get_settings
from .semantic_router import (
    SemanticRouter, 
    get_semantic_router, 
    RouteDecision, 
    IntentCategory
)
from .guardrails import (
    IronDomeGuardrails, 
    get_guardrails, 
    get_content_filter,
    GuardrailResult
)
from .workers import (
    WorkerState,
    fast_responder,
    AyurvedaSpecialist,
    PharmacistAgent,
    DiagnosticsAgent,
    DietCoach,
    get_worker
)
from .graph_memory import get_health_graph_rag, init_user_in_graph


logger = logging.getLogger(__name__)


# === State Definitions ===

class AgentType(str, Enum):
    """Types of agents in the council."""
    FAST_RESPONDER = "fast_responder"
    AYURVEDA_SPECIALIST = "ayurveda_specialist"
    PHARMACIST = "pharmacist"
    DIAGNOSTICS = "diagnostics"
    DIET_COACH = "diet_coach"
    SUPERVISOR = "supervisor"
    FINISH = "finish"


class ClinicalState(TypedDict):
    """
    Global state for the Clinical Council.
    
    This state is shared across all nodes in the graph.
    """
    # Input
    user_id: str
    user_query: str
    messages: list[BaseMessage]
    
    # User context
    dosha_profile: dict
    health_conditions: list[str]
    
    # Routing
    route_decision: Optional[dict]  # RouteDecision as dict
    current_agent: str
    
    # Memory
    graph_context: str  # Retrieved from GraphRAG
    
    # Execution
    worker_outputs: list[str]
    aggregated_response: str
    
    # Safety
    guardrail_result: Optional[dict]  # GuardrailResult as dict
    final_response: str
    is_complete: bool
    progress_callback: Optional[Callable[[str, Optional[str]], Awaitable[None]]]


async def emit_progress(state: ClinicalState, stage: str, detail: Optional[str] = None) -> None:
    callback = state.get("progress_callback")
    if not callback:
        return
    try:
        await callback(stage, detail)
    except Exception:
        logger.exception("progress callback failed")


# === Supervisor Routing Schema ===

class RouterSchema(BaseModel):
    """Schema for supervisor's routing decision."""
    agent_name: Literal["ayurveda_specialist", "pharmacist", "diagnostics", "diet_coach", "finish"] = Field(
        description="The specialist to route to, or 'finish' if no further action needed"
    )
    reasoning: str = Field(
        description="Brief explanation for the routing decision"
    )
    requires_multiple_specialists: bool = Field(
        default=False,
        description="Whether multiple specialists should be consulted"
    )
    additional_specialists: list[str] = Field(
        default_factory=list,
        description="Additional specialists to consult if requires_multiple_specialists is True"
    )


# === Node Functions ===

async def route_input_node(state: ClinicalState) -> dict:
    """
    Initial routing using SemanticRouter (LLM-powered).
    
    This is the "Triage Nurse" - uses LLM for nuanced classification
    with fast regex fallbacks for emergencies and greetings.
    """
    logger.info("route_input_node started")
    await emit_progress(state, "router")
    router = get_semantic_router()
    content_filter = get_content_filter()
    
    # First, check for prompt injection / off-topic (backup to LLM check)
    is_safe, rejection = content_filter.filter_input(state["user_query"])
    if not is_safe:
        logger.info("route_input_node blocked by content filter")
        await emit_progress(state, "response")
        return {
            "final_response": rejection,
            "is_complete": True,
            "current_agent": AgentType.FINISH.value,
            "route_decision": {"intent": "blocked", "confidence": 1.0}
        }
    
    # Classify intent using LLM
    logger.debug("route_input_node invoking semantic router")
    decision = await router.aclassify(state["user_query"])
    
    # Handle emergency immediately
    if decision.intent == IntentCategory.EMERGENCY:
        logger.info("route_input_node emergency route")
        await emit_progress(state, "response")
        return {
            "final_response": decision.fast_response,
            "is_complete": True,
            "current_agent": AgentType.FINISH.value,
            "route_decision": {
                "intent": decision.intent.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning
            }
        }
    
    # Handle unknown/out-of-domain/suspicious queries
    if decision.intent == IntentCategory.UNKNOWN:
        logger.info("route_input_node unknown route")
        await emit_progress(state, "response")
        return {
            "final_response": decision.fast_response,
            "is_complete": True,
            "current_agent": AgentType.FINISH.value,
            "route_decision": {
                "intent": decision.intent.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning
            }
        }
    
    # Handle simple queries with pre-computed response
    if decision.fast_response and not decision.requires_supervisor:
        logger.info("route_input_node fast response route")
        await emit_progress(state, "response")
        return {
            "final_response": decision.fast_response,
            "is_complete": True,
            "current_agent": AgentType.FINISH.value,
            "route_decision": {
                "intent": decision.intent.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning
            }
        }
    
    # Route based on decision
    if not decision.requires_supervisor:
        logger.info("route_input_node fast responder route")
        return {
            "route_decision": {
                "intent": decision.intent.value,
                "confidence": decision.confidence,
                "requires_supervisor": False,
                "reasoning": decision.reasoning
            },
            "current_agent": AgentType.FAST_RESPONDER.value
        }
    
    logger.info("route_input_node supervisor route")
    return {
        "route_decision": {
            "intent": decision.intent.value,
            "confidence": decision.confidence,
            "requires_supervisor": True,
            "reasoning": decision.reasoning
        },
        "current_agent": AgentType.SUPERVISOR.value
    }


async def fast_responder_node(state: ClinicalState) -> dict:
    """
    Handle simple queries with fast, lightweight model.
    """
    logger.info("fast_responder_node started")
    await emit_progress(state, "fast_responder")
    response = await fast_responder(state["user_query"])
    
    return {
        "aggregated_response": response,
        "current_agent": AgentType.FINISH.value
    }


async def retrieve_context_node(state: ClinicalState) -> dict:
    """
    Retrieve relevant context from GraphRAG before supervisor routing.
    """
    logger.info("retrieve_context_node started")
    await emit_progress(state, "context")
    rag = get_health_graph_rag()
    
    # Initialize user if not exists
    init_user_in_graph(
        state["user_id"], 
        state.get("health_conditions", [])
    )
    
    # Retrieve context
    context = rag.retrieve_context(
        state["user_id"],
        state["user_query"]
    )
    logger.info("retrieve_context_node completed")
    return {"graph_context": context}


async def supervisor_node(state: ClinicalState) -> dict:
    """
    The Clinical Director - routes to appropriate specialists.
    
    Uses structured output (function calling) to enforce valid routing.
    """
    logger.info("supervisor_node started")
    await emit_progress(state, "supervisor")
    settings = get_settings()
    
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    llm = ChatOpenAI(
        model=settings.planner_model,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.2,
        timeout=30
    )
    
    system_prompt = """You are the Clinical Director of an Ayurvedic wellness center.
Your role is to route patient queries to the most appropriate specialist.

Available Specialists:
- ayurveda_specialist: For Dosha analysis, Prakriti/Vikriti assessment, constitution questions
- pharmacist: For herb safety, drug interactions, contraindications, supplement questions
- diagnostics: For symptom analysis, pattern recognition, wellness mapping
- diet_coach: For dietary advice, meal planning, lifestyle routines, exercise

Patient Context:
- Dosha Profile: {dosha_profile}
- Known Conditions: {health_conditions}
- Historical Context: {graph_context}

ROUTING RULES:
1. If the query involves herbs, medications, or "can I take X with Y" → pharmacist FIRST
2. If symptoms are mentioned → diagnostics
3. If asking about body type, constitution, or Dosha → ayurveda_specialist
4. If asking about food, diet, or daily routine → diet_coach
5. Complex queries may need multiple specialists (set requires_multiple_specialists=True)

Route to 'finish' ONLY if the query is already answered or invalid."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Route this query: {query}")
    ])
    
    # Use structured output for reliable routing
    try:
        structured_llm = llm.with_structured_output(RouterSchema)
        chain = prompt | structured_llm
        format_instructions = None
    except NotImplementedError:
        parser = PydanticOutputParser(pydantic_object=RouterSchema)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + "\n\n{format_instructions}"),
            ("human", "Route this query: {query}")
        ])
        chain = prompt | llm | parser
        format_instructions = parser.get_format_instructions()
    
    try:
        logger.debug("supervisor_node invoking LLM chain")
        invoke_payload = {
            "dosha_profile": state.get("dosha_profile", {}),
            "health_conditions": state.get("health_conditions", []),
            "graph_context": state.get("graph_context", "No history"),
            "query": state["user_query"]
        }
        if format_instructions:
            invoke_payload["format_instructions"] = format_instructions

        result = await chain.ainvoke(invoke_payload)
        logger.info("supervisor_node routed to %s", result.agent_name)
        return {
            "current_agent": result.agent_name,
            "worker_outputs": []  # Reset for new specialist
        }
        
    except Exception as e:
        logger.exception("supervisor_node failed; defaulting to diagnostics")
        # Fallback to diagnostics for general health queries
        return {
            "current_agent": AgentType.DIAGNOSTICS.value
        }


async def ayurveda_specialist_node(state: ClinicalState) -> dict:
    """Execute the Ayurveda Specialist worker."""
    logger.info("ayurveda_specialist_node started")
    await emit_progress(state, "worker", "ayurveda_specialist")
    worker = AyurvedaSpecialist()
    
    worker_state: WorkerState = {
        "messages": state.get("messages", []),
        "user_query": state["user_query"],
        "dosha_profile": state.get("dosha_profile", {}),
        "health_conditions": state.get("health_conditions", []),
        "context_from_graph": state.get("graph_context"),
        "worker_output": "",
        "needs_followup": False
    }
    
    result = await worker.process(worker_state)
    
    outputs = state.get("worker_outputs", [])
    outputs.append(result["worker_output"])
    
    return {
        "worker_outputs": outputs,
        "current_agent": AgentType.SUPERVISOR.value  # Return to supervisor for potential follow-up
    }


async def pharmacist_node(state: ClinicalState) -> dict:
    """Execute the Pharmacist worker."""
    logger.info("pharmacist_node started")
    await emit_progress(state, "worker", "pharmacist")
    worker = PharmacistAgent()
    
    worker_state: WorkerState = {
        "messages": state.get("messages", []),
        "user_query": state["user_query"],
        "dosha_profile": state.get("dosha_profile", {}),
        "health_conditions": state.get("health_conditions", []),
        "context_from_graph": state.get("graph_context"),
        "worker_output": "",
        "needs_followup": False
    }
    
    result = await worker.process(worker_state)
    
    outputs = state.get("worker_outputs", [])
    outputs.append(result["worker_output"])
    
    return {
        "worker_outputs": outputs,
        "current_agent": AgentType.SUPERVISOR.value
    }


async def diagnostics_node(state: ClinicalState) -> dict:
    """Execute the Diagnostics worker."""
    logger.info("diagnostics_node started")
    await emit_progress(state, "worker", "diagnostics")
    worker = DiagnosticsAgent()
    
    worker_state: WorkerState = {
        "messages": state.get("messages", []),
        "user_query": state["user_query"],
        "dosha_profile": state.get("dosha_profile", {}),
        "health_conditions": state.get("health_conditions", []),
        "context_from_graph": state.get("graph_context"),
        "worker_output": "",
        "needs_followup": False
    }
    
    result = await worker.process(worker_state)
    
    outputs = state.get("worker_outputs", [])
    outputs.append(result["worker_output"])
    
    return {
        "worker_outputs": outputs,
        "current_agent": AgentType.SUPERVISOR.value
    }


async def diet_coach_node(state: ClinicalState) -> dict:
    """Execute the Diet Coach worker."""
    logger.info("diet_coach_node started")
    await emit_progress(state, "worker", "diet_coach")
    worker = DietCoach()
    
    worker_state: WorkerState = {
        "messages": state.get("messages", []),
        "user_query": state["user_query"],
        "dosha_profile": state.get("dosha_profile", {}),
        "health_conditions": state.get("health_conditions", []),
        "context_from_graph": state.get("graph_context"),
        "worker_output": "",
        "needs_followup": False
    }
    
    result = await worker.process(worker_state)
    
    outputs = state.get("worker_outputs", [])
    outputs.append(result["worker_output"])
    
    return {
        "worker_outputs": outputs,
        "current_agent": AgentType.SUPERVISOR.value
    }


async def aggregator_node(state: ClinicalState) -> dict:
    """
    Aggregate outputs from multiple workers into a coherent response.
    """
    logger.info("aggregator_node started")
    await emit_progress(state, "aggregation")
    outputs = state.get("worker_outputs", [])
    
    if not outputs:
        return {
            "aggregated_response": "I apologize, but I couldn't generate a response. Please try rephrasing your question."
        }
    
    if len(outputs) == 1:
        return {"aggregated_response": outputs[0]}
    
    # Multiple outputs - combine them
    settings = get_settings()
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    llm = ChatOpenAI(
        model=settings.executor_model or "gpt-4o-mini",
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.3,
        timeout=30
    )
    
    synthesis_prompt = ChatPromptTemplate.from_messages([
        ("system", """Synthesize these specialist responses into a coherent, unified answer.
Maintain the key points from each specialist. Avoid redundancy.
Structure the response clearly with headers if multiple topics are covered.
Keep the tone warm and supportive."""),
        ("human", "Query: {query}\n\nSpecialist Responses:\n{responses}")
    ])
    
    chain = synthesis_prompt | llm
    
    try:
        logger.debug("aggregator_node invoking LLM chain")
        result = await chain.ainvoke({
            "query": state["user_query"],
            "responses": "\n\n---\n\n".join(outputs)
        })
        logger.info("aggregator_node completed")
        return {"aggregated_response": result.content}
    except:
        logger.exception("aggregator_node failed; using fallback concatenation")
        # Fallback: just concatenate
        return {"aggregated_response": "\n\n---\n\n".join(outputs)}


async def guardrail_node(state: ClinicalState) -> dict:
    """
    Apply Iron Dome guardrails to the aggregated response.
    
    This is the deterministic safety layer that replaces the LLM reviewer.
    """
    logger.info("guardrail_node started")
    await emit_progress(state, "guardrail")
    guardrails = get_guardrails()
    
    response = state.get("aggregated_response", "")
    result = guardrails.evaluate(response)
    
    if result.passed:
        logger.info("guardrail_node passed")
        return {
            "final_response": result.sanitized_output or response,
            "guardrail_result": {
                "passed": True,
                "violations": [
                    {"rule": v.rule_name, "severity": v.severity}
                    for v in result.violations
                ]
            },
            "is_complete": True
        }
    else:
        logger.info("guardrail_node blocked")
        return {
            "final_response": result.fallback_message,
            "guardrail_result": {
                "passed": False,
                "violations": [
                    {"rule": v.rule_name, "severity": v.severity, "reason": v.reason}
                    for v in result.violations
                ]
            },
            "is_complete": True
        }


def should_continue_to_worker(state: ClinicalState) -> str:
    """Determine next step based on current_agent."""
    if state.get("is_complete"):
        return END
        
    agent = state.get("current_agent", "")
    
    if agent == AgentType.FINISH.value:
        # Check if we need guardrails
        if state.get("aggregated_response"):
            return "guardrail"
        return END
    
    if agent == AgentType.FAST_RESPONDER.value:
        return "fast_responder"
    
    if agent == AgentType.SUPERVISOR.value:
        # Check if we've already processed workers
        if state.get("worker_outputs"):
            return "aggregator"
        return "retrieve_context"
    
    # Route to specific workers
    worker_map = {
        AgentType.AYURVEDA_SPECIALIST.value: "ayurveda_specialist",
        AgentType.PHARMACIST.value: "pharmacist",
        AgentType.DIAGNOSTICS.value: "diagnostics",
        AgentType.DIET_COACH.value: "diet_coach",
    }
    
    return worker_map.get(agent, "aggregator")


def should_return_to_supervisor(state: ClinicalState) -> str:
    """After worker execution, decide if more work is needed."""
    # For now, always aggregate after one worker
    # Future: check if requires_multiple_specialists was set
    outputs = state.get("worker_outputs", [])
    
    if outputs:
        return "aggregator"
    return "supervisor"


# === Graph Construction ===

def create_clinical_council() -> StateGraph:
    """
    Build the Hierarchical Clinical Council workflow.
    
    Flow:
    1. route_input: Semantic router classifies intent
    2a. Simple → fast_responder → guardrail → END
    2b. Complex → retrieve_context → supervisor → worker(s) → aggregator → guardrail → END
    """
    workflow = StateGraph(ClinicalState)
    
    # Add all nodes
    workflow.add_node("route_input", route_input_node)
    workflow.add_node("fast_responder", fast_responder_node)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("ayurveda_specialist", ayurveda_specialist_node)
    workflow.add_node("pharmacist", pharmacist_node)
    workflow.add_node("diagnostics", diagnostics_node)
    workflow.add_node("diet_coach", diet_coach_node)
    workflow.add_node("aggregator", aggregator_node)
    workflow.add_node("guardrail", guardrail_node)
    
    # Entry point
    workflow.set_entry_point("route_input")
    
    # Conditional routing from input
    workflow.add_conditional_edges(
        "route_input",
        should_continue_to_worker,
        {
            "fast_responder": "fast_responder",
            "retrieve_context": "retrieve_context",
            "guardrail": "guardrail",
            END: END
        }
    )
    
    # Fast responder → guardrail
    workflow.add_edge("fast_responder", "guardrail")
    
    # Context retrieval → supervisor
    workflow.add_edge("retrieve_context", "supervisor")
    
    # Supervisor → workers (conditional)
    workflow.add_conditional_edges(
        "supervisor",
        should_continue_to_worker,
        {
            "ayurveda_specialist": "ayurveda_specialist",
            "pharmacist": "pharmacist",
            "diagnostics": "diagnostics",
            "diet_coach": "diet_coach",
            "aggregator": "aggregator",
        }
    )
    
    # Workers → aggregator (for simplicity, direct to aggregator)
    for worker in ["ayurveda_specialist", "pharmacist", "diagnostics", "diet_coach"]:
        workflow.add_edge(worker, "aggregator")
    
    # Aggregator → guardrail
    workflow.add_edge("aggregator", "guardrail")
    
    # Guardrail → END
    workflow.add_edge("guardrail", END)
    
    return workflow.compile()


# === Public API ===

async def process_query(
    user_id: str,
    query: str,
    dosha_profile: Optional[dict] = None,
    health_conditions: Optional[list[str]] = None,
    messages: Optional[list[BaseMessage]] = None,
    progress_callback: Optional[Callable[[str, Optional[str]], Awaitable[None]]] = None
) -> dict:
    """
    Process a user query through the Clinical Council.
    
    This is the main entry point for the agentic system.
    
    Args:
        user_id: Unique user identifier
        query: User's question or message
        dosha_profile: Optional Dosha scores (vata, pitta, kapha)
        health_conditions: Known health conditions for safety checks
        messages: Optional conversation history
    
    Returns:
        Dict with response, safety info, and metadata
    """
    logger.info("process_query started")
    council = create_clinical_council()
    
    initial_state: ClinicalState = {
        "user_id": user_id,
        "user_query": query,
        "messages": messages or [],
        "dosha_profile": dosha_profile or {"vata": 0.33, "pitta": 0.33, "kapha": 0.34},
        "health_conditions": health_conditions or [],
        "route_decision": None,
        "current_agent": "",
        "graph_context": "",
        "worker_outputs": [],
        "aggregated_response": "",
        "guardrail_result": None,
        "final_response": "",
        "is_complete": False,
        "progress_callback": progress_callback
    }
    
    try:
        result = await council.ainvoke(initial_state)
    except Exception as e:
        logger.exception("process_query failed")
        raise
    
    logger.info("process_query completed")
    guardrail_result = result.get("guardrail_result") or {}

    final_response = result.get("final_response") or "I apologize, but I couldn't generate a response. Please try again."

    return {
        "response": final_response,
        "route": result.get("route_decision", {}).get("intent", "unknown"),
        "guardrail_passed": guardrail_result.get("passed", True),
        "guardrail_violations": guardrail_result.get("violations", []),
        "workers_consulted": len(result.get("worker_outputs", [])),
    }
