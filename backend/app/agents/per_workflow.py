"""
LangGraph Planner-Executor-Reviewer (PER) Workflow

Implements agentic treatment planning with self-correction capabilities.
Uses GPT-4o for planning, Llama-3 for execution (cost optimization).
"""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from ..config import get_settings
from .tools import ayurveda_tools


class AgentState(TypedDict):
    """State maintained throughout the PER workflow."""
    # Input
    user_query: str
    dosha_context: dict  # User's Prakriti/Vikriti
    health_conditions: list[str]  # Known conditions for contraindication checking
    
    # Workflow State
    plan: list[str]  # Steps to execute
    current_step_index: int
    past_steps: list[tuple[str, str]]  # (step, result) pairs
    
    # Output
    response: str
    safety_notes: list[str]
    is_safe: bool  # Reviewer verdict


# === SYSTEM PROMPTS ===

PLANNER_SYSTEM = """You are an expert Ayurvedic treatment planner. Your role is to break down user wellness queries into actionable steps.

CONTEXT:
- User's Dosha Profile: {dosha_context}
- Known Health Conditions: {health_conditions}

RULES:
1. Always start by assessing the user's current state if vitals are provided
2. Check contraindications for ANY herb before recommending
3. Provide diet recommendations aligned with their Dosha
4. Never claim to diagnose or treat diseases - this is wellness/educational support only

OUTPUT FORMAT:
Return a numbered list of 3-5 specific steps. Each step should be actionable by calling one of the available tools.

Example:
1. Assess current Dosha state from provided vitals
2. Check contraindications for suggested herbs given user's conditions
3. Get personalized diet recommendations for Vata balancing
4. Compile final wellness recommendations
"""

EXECUTOR_SYSTEM = """You are an Ayurvedic wellness assistant executing a specific step in a treatment plan.

CURRENT STEP TO EXECUTE: {current_step}

Use the available tools to complete this step. Be precise and factual.
If a tool call fails, report the failure clearly.

Available tools can:
- Assess Dosha from questionnaire answers or vitals
- Check herb contraindications
- Get diet recommendations by Dosha type
"""

REVIEWER_SYSTEM = """You are a safety reviewer for Ayurvedic wellness recommendations.

Review the following recommendation for safety issues:

PLAN EXECUTED:
{executed_steps}

FINAL RESPONSE:
{response}

USER'S HEALTH CONDITIONS: {health_conditions}

REVIEW CHECKLIST:
1. Are there any herb recommendations that contradict the user's health conditions?
2. Does the response avoid making medical diagnostic claims?
3. Are all recommendations sourced/traceable?
4. Is there an appropriate disclaimer?

If safe, respond with: "APPROVED: [brief note]"
If unsafe, respond with: "REJECTED: [specific issue] | CORRECTION: [what to fix]"
"""


def get_planner_llm():
    """High-intelligence model for planning (GPT-4o)."""
    settings = get_settings()
    model_name = settings.per_planner_model or settings.planner_model
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.3,  # Lower temperature for consistent planning
        timeout=60
    )


def get_executor_llm():
    """Cost-effective model for execution (Llama-3.3-70B via Groq)."""
    settings = get_settings()
    # If Groq key available, use Llama; otherwise fall back to OpenAI
    if settings.groq_api_key:
        model_name = settings.per_executor_model or settings.executor_model
        return ChatGroq(
            model=model_name,
            api_key=settings.groq_api_key,
            temperature=0.2,
            timeout=60
        )
    # Fallback to OpenAI
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    return ChatOpenAI(
        model="gpt-4o-mini",  # Cost-effective OpenAI fallback
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.2,
        timeout=60
    )


def get_synthesizer_llm():
    """Model for synthesis in the PER workflow."""
    settings = get_settings()
    model_name = settings.per_synthesizer_model or settings.planner_model
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.3,
        timeout=60
    )


def get_reviewer_llm():
    """Reviewer uses planner model for thorough safety checks."""
    settings = get_settings()
    model_name = settings.per_reviewer_model or settings.planner_model
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.3,
        timeout=60
    )


# === NODE FUNCTIONS ===

def planner_node(state: AgentState) -> dict:
    """Creates a step-by-step plan from user query."""
    llm = get_planner_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_SYSTEM),
        ("human", "{query}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "dosha_context": state["dosha_context"],
        "health_conditions": state.get("health_conditions", []),
        "query": state["user_query"]
    })
    
    # Parse steps from response
    lines = response.content.strip().split("\n")
    steps = [
        line.strip().lstrip("0123456789.").strip()
        for line in lines
        if line.strip() and line.strip()[0].isdigit()
    ]
    
    if not steps:
        steps = ["Provide general Dosha-based wellness advice"]
    
    return {
        "plan": steps,
        "current_step_index": 0,
        "past_steps": []
    }


def executor_node(state: AgentState) -> dict:
    """Executes the current step using tools."""
    if state["current_step_index"] >= len(state["plan"]):
        return {}  # No more steps
    
    current_step = state["plan"][state["current_step_index"]]
    llm = get_executor_llm()
    
    # Bind tools to the executor
    llm_with_tools = llm.bind_tools(ayurveda_tools)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXECUTOR_SYSTEM),
        ("human", "Execute this step for the user's wellness plan.")
    ])
    
    chain = prompt | llm_with_tools
    
    try:
        response = chain.invoke({"current_step": current_step})
        
        # Process tool calls if any
        result_parts = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Find and execute the tool
                for tool in ayurveda_tools:
                    if tool.name == tool_name:
                        tool_result = tool.invoke(tool_args)
                        result_parts.append(f"[{tool_name}]: {tool_result}")
                        break
        
        if result_parts:
            result = "\n".join(result_parts)
        else:
            result = response.content or "Step completed (no tool output)"
            
    except Exception as e:
        result = f"Error executing step: {str(e)}"
    
    # Update past steps
    new_past_steps = state["past_steps"] + [(current_step, result)]
    
    return {
        "past_steps": new_past_steps,
        "current_step_index": state["current_step_index"] + 1
    }


def should_continue_execution(state: AgentState) -> str:
    """Determine if we should continue executing or move to synthesis."""
    if state["current_step_index"] >= len(state["plan"]):
        return "synthesize"
    return "execute"


def synthesize_node(state: AgentState) -> dict:
    """Compile all step results into a coherent response."""
    llm = get_synthesizer_llm()
    
    executed_summary = "\n".join([
        f"Step: {step}\nResult: {result}"
        for step, result in state["past_steps"]
    ])
    
    synthesis_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are compiling wellness recommendations from executed steps.
        
Create a clear, organized response that:
1. Summarizes the user's Dosha assessment
2. Lists specific, actionable recommendations
3. Notes any safety considerations
4. Includes a wellness disclaimer

Be warm but professional. Use formatting for clarity."""),
        ("human", f"User Query: {state['user_query']}\n\nExecuted Steps:\n{executed_summary}")
    ])
    
    chain = synthesis_prompt | llm
    response = chain.invoke({})
    
    return {
        "response": response.content,
        "safety_notes": []  # Will be populated by reviewer
    }


def reviewer_node(state: AgentState) -> dict:
    """Review the final response for safety."""
    llm = get_reviewer_llm()
    
    executed_summary = "\n".join([
        f"- {step}: {result[:200]}..."
        for step, result in state["past_steps"]
    ])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", REVIEWER_SYSTEM),
        ("human", "Review this recommendation for safety.")
    ])
    
    chain = prompt | llm
    review = chain.invoke({
        "executed_steps": executed_summary,
        "response": state["response"],
        "health_conditions": state.get("health_conditions", [])
    })
    
    review_text = review.content.upper()
    is_safe = "APPROVED" in review_text
    
    safety_notes = []
    if not is_safe and "CORRECTION:" in review.content:
        correction = review.content.split("CORRECTION:")[-1].strip()
        safety_notes.append(f"Review note: {correction}")
    
    return {
        "is_safe": is_safe,
        "safety_notes": safety_notes
    }


def handle_rejection(state: AgentState) -> dict:
    """Handle rejected recommendations by adding safety warnings."""
    # Append safety disclaimer to response
    safe_response = (
        state["response"] + 
        "\n\n⚠️ **Safety Note**: " + 
        " ".join(state["safety_notes"]) +
        "\n\nPlease consult a qualified Ayurvedic practitioner before following these recommendations."
    )
    return {"response": safe_response, "is_safe": True}


def should_finalize(state: AgentState) -> str:
    """Determine if response is safe to return or needs correction."""
    if state.get("is_safe", False):
        return END
    return "handle_rejection"


# === GRAPH CONSTRUCTION ===

def create_treatment_agent() -> StateGraph:
    """
    Build the LangGraph PER workflow.
    
    Flow:
    1. Planner creates steps
    2. Executor runs each step (loops until done)
    3. Synthesizer compiles response
    4. Reviewer checks safety
    5. If rejected, add warnings and finalize
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes  
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("handle_rejection", handle_rejection)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add edges
    workflow.add_edge("planner", "executor")
    
    # Conditional: continue execution or synthesize
    workflow.add_conditional_edges(
        "executor",
        should_continue_execution,
        {
            "execute": "executor",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_edge("synthesize", "reviewer")
    
    # Conditional: finalize or handle rejection
    workflow.add_conditional_edges(
        "reviewer",
        should_finalize,
        {
            END: END,
            "handle_rejection": "handle_rejection"
        }
    )
    
    workflow.add_edge("handle_rejection", END)
    
    return workflow.compile()


# Convenience function for direct invocation
async def generate_treatment_plan(
    user_query: str,
    dosha_context: dict,
    health_conditions: list[str] | None = None
) -> dict:
    """
    Generate a personalized treatment plan using the PER agent.
    
    Args:
        user_query: User's wellness question
        dosha_context: Dict with vata, pitta, kapha scores
        health_conditions: List of known conditions for safety checks
    
    Returns:
        Dict with response, safety_notes, and is_safe flag
    """
    agent = create_treatment_agent()
    
    initial_state: AgentState = {
        "user_query": user_query,
        "dosha_context": dosha_context,
        "health_conditions": health_conditions or [],
        "plan": [],
        "current_step_index": 0,
        "past_steps": [],
        "response": "",
        "safety_notes": [],
        "is_safe": False
    }
    
    result = await agent.ainvoke(initial_state)
    
    return {
        "response": result["response"],
        "safety_notes": result["safety_notes"],
        "is_safe": result["is_safe"],
        "steps_executed": len(result["past_steps"])
    }
