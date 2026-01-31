"""
Multi-Agent Debate Protocol - Ayurveda vs Biomedical Critique

A structured debate workflow where:
1. Ayurveda Expert proposes recommendations (with RAG access)
2. Biomedical Expert critiques from evidence-based perspective (no RAG)
3. Ayurveda Expert revises based on critique
4. Risk Mapper performs deterministic safety checks
5. Orchestration Scorer evaluates the debate quality
6. Final response passes through IronDome Guardrails

This ensures balanced, safe recommendations that respect both
traditional Ayurvedic wisdom and modern biomedical evidence.
"""

from typing import TypedDict, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..config import get_settings
from .guardrails import IronDomeGuardrails, get_guardrails, GuardrailResult
from .workers import (
    WorkerState,
    AyurvedaSpecialist,
    BiomedicalCritic,
    get_specialist_llm
)
from .graph_memory import get_health_graph_rag, init_user_in_graph
from .tools import check_contraindication


logger = logging.getLogger(__name__)


# === Scoring Models ===

class RiskLevel(str, Enum):
    """Risk levels for recommendations."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskItem:
    """A single risk identified in recommendations."""
    herb_or_action: str
    condition: str
    severity: str
    reason: str
    source: str


@dataclass
class RiskMap:
    """Complete risk mapping for a recommendation set."""
    risks: list[RiskItem] = field(default_factory=list)
    overall_risk_level: RiskLevel = RiskLevel.LOW
    safe_recommendations: list[str] = field(default_factory=list)
    flagged_recommendations: list[str] = field(default_factory=list)


class DebateScores(BaseModel):
    """Structured scores from the debate orchestration."""
    evidence_score: float = Field(
        ge=0.0, le=10.0,
        description="How well-supported are the recommendations by evidence (0-10)"
    )
    safety_score: float = Field(
        ge=0.0, le=10.0,
        description="How safe are the recommendations given user's conditions (0-10)"
    )
    integration_score: float = Field(
        ge=0.0, le=10.0,
        description="How well were biomedical concerns addressed in revision (0-10)"
    )
    practicality_score: float = Field(
        ge=0.0, le=10.0,
        description="How practical and actionable are the recommendations (0-10)"
    )
    final_score: float = Field(
        ge=0.0, le=10.0,
        description="Overall weighted score (0-10)"
    )
    score_reasoning: str = Field(
        description="Brief explanation of the scoring"
    )
    recommendation_tier: str = Field(
        description="Tier: 'Highly Recommended', 'Recommended with Caution', 'Not Recommended', 'Requires Professional Supervision'"
    )


# === Debate State ===

class DebateState(TypedDict):
    """
    State for the multi-agent debate workflow.
    
    Tracks both experts' outputs and scoring throughout the debate.
    """
    # Input
    user_id: str
    user_query: str
    messages: list[BaseMessage]
    
    # User context
    dosha_profile: dict
    health_conditions: list[str]
    
    # GraphRAG context (only for Ayurveda expert)
    graph_context: str
    
    # Debate rounds
    ayurveda_proposal: str
    biomedical_critique: str
    ayurveda_revision: str
    
    # Risk assessment
    risk_map: Optional[dict]  # RiskMap as dict
    
    # Scoring
    debate_scores: Optional[dict]  # DebateScores as dict
    
    # Final output
    final_response: str
    guardrail_result: Optional[dict]
    is_complete: bool
    
    # Progress callback for streaming
    progress_callback: Optional[Callable[[str, Optional[str]], Awaitable[None]]]


async def emit_progress(state: DebateState, stage: str, detail: Optional[str] = None) -> None:
    """Emit progress update if callback is provided."""
    callback = state.get("progress_callback")
    if not callback:
        return
    try:
        await callback(stage, detail)
    except Exception:
        logger.exception("Progress callback failed")


# === Node Functions ===

async def retrieve_context_node(state: DebateState) -> dict:
    """
    Retrieve GraphRAG context for the Ayurveda expert only.
    
    The Biomedical expert intentionally does NOT receive this context
    to maintain an unbiased evidence-based perspective.
    """
    logger.info("retrieve_context_node started (debate)")
    await emit_progress(state, "context", "Retrieving health history")
    
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


async def ayurveda_proposal_node(state: DebateState) -> dict:
    """
    Generate initial Ayurvedic recommendation.
    
    The Ayurveda expert has access to:
    - GraphRAG context (user health history)
    - Dosha profile
    - Health conditions
    - Ayurvedic tools
    """
    logger.info("ayurveda_proposal_node started")
    await emit_progress(state, "ayurveda_proposal", "Generating Ayurvedic recommendations")
    
    specialist = AyurvedaSpecialist()
    
    worker_state: WorkerState = {
        "messages": state.get("messages", []),
        "user_query": state["user_query"],
        "dosha_profile": state.get("dosha_profile", {}),
        "health_conditions": state.get("health_conditions", []),
        "context_from_graph": state.get("graph_context"),
        "worker_output": "",
        "needs_followup": False
    }
    
    result = await specialist.process(worker_state)
    
    logger.info("ayurveda_proposal_node completed")
    return {"ayurveda_proposal": result["worker_output"]}


async def biomedical_critique_node(state: DebateState) -> dict:
    """
    Generate biomedical critique of the Ayurvedic proposal.
    
    The Biomedical expert has access to:
    - Health conditions (important for safety)
    - The Ayurvedic proposal to critique
    
    The Biomedical expert does NOT have access to:
    - GraphRAG context (to avoid bias)
    - Ayurvedic tools
    - Dosha profile (irrelevant to biomedical perspective)
    """
    logger.info("biomedical_critique_node started")
    await emit_progress(state, "biomedical_critique", "Biomedical expert reviewing")
    
    critic = BiomedicalCritic()
    
    worker_state: WorkerState = {
        "messages": [],  # No conversation history for unbiased review
        "user_query": state["user_query"],
        "dosha_profile": {},  # Not provided to biomedical expert
        "health_conditions": state.get("health_conditions", []),
        "context_from_graph": None,  # Explicitly no RAG access
        "worker_output": "",
        "needs_followup": False
    }
    
    result = await critic.process(worker_state, ayurveda_proposal=state["ayurveda_proposal"])
    
    logger.info("biomedical_critique_node completed")
    return {"biomedical_critique": result["worker_output"]}


AYURVEDA_REVISION_SYSTEM = """You are a senior Ayurvedic Vaidya (physician) revising your recommendations.

You previously provided Ayurvedic recommendations that have been reviewed by a biomedical expert.
Your task is to revise your recommendations considering the biomedical critique while
maintaining the wisdom of Ayurvedic principles where safe and appropriate.

USER'S PROFILE:
- Dosha Scores: {dosha_profile}
- Known Health Conditions: {health_conditions}

CONTEXT FROM PREVIOUS SESSIONS:
{context_from_graph}

YOUR ORIGINAL PROPOSAL:
{original_proposal}

BIOMEDICAL CRITIQUE:
{biomedical_critique}

REVISION GUIDELINES:
1. Accept valid safety concerns - patient safety is paramount
2. Modify or remove recommendations flagged as high-risk
3. Provide alternatives where original recommendations are contraindicated
4. Explain your reasoning for keeping recommendations you believe are safe
5. Add appropriate caveats and monitoring suggestions
6. Maintain Ayurvedic principles where they don't conflict with safety

OUTPUT FORMAT:
1. **Accepted Concerns**: List which critique points you're addressing
2. **Maintained Recommendations**: What you're keeping and why (with safety notes)
3. **Modified Recommendations**: What you've changed based on critique
4. **Removed Recommendations**: What you've removed as too risky
5. **Alternative Suggestions**: Safe alternatives for removed items
6. **Final Integrated Plan**: Your revised, safety-conscious recommendations

Be humble about limitations while confident about well-established Ayurvedic practices."""


async def ayurveda_revision_node(state: DebateState) -> dict:
    """
    Ayurveda expert revises recommendations based on biomedical critique.
    
    This is the key "self-correction" step where the Ayurveda model
    integrates valid biomedical concerns while maintaining appropriate
    traditional practices.
    """
    logger.info("ayurveda_revision_node started")
    await emit_progress(state, "ayurveda_revision", "Integrating feedback and revising")
    
    settings = get_settings()
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    model_name = settings.debate_revision_model or settings.planner_model
    
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.4,
        timeout=90
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", AYURVEDA_REVISION_SYSTEM),
        ("human", "Please provide your revised recommendations considering the biomedical critique.")
    ])
    
    chain = prompt | llm
    
    try:
        response = await chain.ainvoke({
            "dosha_profile": state.get("dosha_profile", {}),
            "health_conditions": state.get("health_conditions", []),
            "context_from_graph": state.get("graph_context", "No history"),
            "original_proposal": state["ayurveda_proposal"],
            "biomedical_critique": state["biomedical_critique"]
        })
        
        logger.info("ayurveda_revision_node completed")
        return {"ayurveda_revision": response.content}
        
    except Exception as e:
        logger.exception("ayurveda_revision_node failed")
        return {
            "ayurveda_revision": (
                f"Unable to complete revision. Original proposal with caution advisory:\n\n"
                f"{state['ayurveda_proposal']}\n\n"
                f"⚠️ Please consult a healthcare professional before following these recommendations."
            )
        }


# Herb extraction patterns for risk mapping
HERB_PATTERNS = [
    r'\b(ashwagandha|withania)\b',
    r'\b(brahmi|bacopa)\b',
    r'\b(triphala|amalaki|bibhitaki|haritaki)\b',
    r'\b(turmeric|curcumin|haldi)\b',
    r'\b(ginger|zingiber|shunti)\b',
    r'\b(guggulu?|commiphora)\b',
    r'\b(shatavari|asparagus)\b',
    r'\b(tulsi|holy\s*basil)\b',
    r'\b(neem|azadirachta)\b',
    r'\b(amla|amalaki|emblica)\b',
    r'\b(licorice|mulethi|yashtimadhu)\b',
    r'\b(boswellia|shallaki)\b',
    r'\b(giloy|guduchi|tinospora)\b',
    r'\b(arjuna|terminalia)\b',
    r'\b(punarnava|boerhavia)\b',
]


def extract_herbs_from_text(text: str) -> list[str]:
    """Extract mentioned herbs from recommendation text."""
    herbs = []
    text_lower = text.lower()
    
    for pattern in HERB_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        if matches:
            # Normalize herb names
            herb_name = matches[0] if isinstance(matches[0], str) else matches[0][0]
            # Map to canonical names
            canonical = {
                "withania": "ashwagandha",
                "bacopa": "brahmi",
                "curcumin": "turmeric",
                "haldi": "turmeric",
                "zingiber": "ginger",
                "shunti": "ginger",
                "holy basil": "tulsi",
                "azadirachta": "neem",
                "emblica": "amla",
                "amalaki": "amla",
                "mulethi": "licorice",
                "yashtimadhu": "licorice",
                "shallaki": "boswellia",
                "guduchi": "giloy",
                "tinospora": "giloy",
                "terminalia": "arjuna",
                "boerhavia": "punarnava",
            }.get(herb_name, herb_name)
            
            if canonical not in herbs:
                herbs.append(canonical)
    
    return herbs


async def risk_mapper_node(state: DebateState) -> dict:
    """
    Perform deterministic risk mapping using contraindication database.
    
    This node:
    1. Extracts herbs mentioned in the revised recommendations
    2. Checks each against user's health conditions
    3. Builds a structured risk map
    
    Uses the same contraindication tool as PharmacistAgent for consistency.
    """
    logger.info("risk_mapper_node started")
    await emit_progress(state, "risk_mapping", "Checking contraindications")
    
    revision_text = state.get("ayurveda_revision", "")
    health_conditions = state.get("health_conditions", [])
    
    # Extract herbs from the revised recommendations
    herbs = extract_herbs_from_text(revision_text)
    
    risks: list[dict] = []
    safe_herbs: list[str] = []
    flagged_herbs: list[str] = []
    
    # Check each herb against each condition
    for herb in herbs:
        herb_flagged = False
        for condition in health_conditions:
            # Use the deterministic contraindication tool
            result = check_contraindication.invoke({
                "herb_name": herb,
                "condition": condition
            })
            
            # Parse the result to determine if there's a contraindication
            if "CONTRAINDICATION FOUND" in result or "⚠️" in result:
                herb_flagged = True
                
                # Extract severity from result
                severity = "MODERATE"
                if "HIGH" in result:
                    severity = "HIGH"
                elif "CRITICAL" in result:
                    severity = "CRITICAL"
                elif "LOW" in result:
                    severity = "LOW"
                
                risks.append({
                    "herb_or_action": herb,
                    "condition": condition,
                    "severity": severity,
                    "reason": result,
                    "source": "Contraindication Database"
                })
                
                if herb not in flagged_herbs:
                    flagged_herbs.append(herb)
        
        if not herb_flagged and herb not in safe_herbs:
            safe_herbs.append(herb)
    
    # Determine overall risk level
    overall_risk = RiskLevel.LOW
    if any(r["severity"] == "CRITICAL" for r in risks):
        overall_risk = RiskLevel.CRITICAL
    elif any(r["severity"] == "HIGH" for r in risks):
        overall_risk = RiskLevel.HIGH
    elif any(r["severity"] == "MODERATE" for r in risks):
        overall_risk = RiskLevel.MODERATE
    
    risk_map = {
        "risks": risks,
        "overall_risk_level": overall_risk.value,
        "safe_recommendations": safe_herbs,
        "flagged_recommendations": flagged_herbs
    }
    
    logger.info("risk_mapper_node completed: %d risks found, overall=%s", 
                len(risks), overall_risk.value)
    return {"risk_map": risk_map}


ORCHESTRATION_SCORER_SYSTEM = """You are a Clinical Quality Assessor evaluating an Ayurveda-Biomedical debate.

Your task is to score the quality of the debate and final recommendations.

ORIGINAL AYURVEDIC PROPOSAL:
{ayurveda_proposal}

BIOMEDICAL CRITIQUE:
{biomedical_critique}

REVISED AYURVEDIC RECOMMENDATIONS:
{ayurveda_revision}

DETERMINISTIC RISK ASSESSMENT:
{risk_map}

USER'S HEALTH CONDITIONS:
{health_conditions}

SCORING CRITERIA:

1. **Evidence Score (0-10)**: How well-supported are the final recommendations?
   - 0-3: Claims without evidence or contradicted by evidence
   - 4-6: Traditional use with some supporting research
   - 7-10: Well-supported by clinical evidence

2. **Safety Score (0-10)**: How safe given the user's conditions?
   - 0-3: High/critical risks present, inadequate warnings
   - 4-6: Moderate risks with appropriate caveats
   - 7-10: Low risk, contraindications properly addressed

3. **Integration Score (0-10)**: How well were biomedical concerns addressed?
   - 0-3: Concerns dismissed or ignored
   - 4-6: Partial integration, some concerns unaddressed
   - 7-10: Thoughtful integration, concerns properly addressed

4. **Practicality Score (0-10)**: How actionable are the recommendations?
   - 0-3: Vague or impractical suggestions
   - 4-6: Generally practical with some unclear points
   - 7-10: Clear, specific, implementable recommendations

5. **Final Score**: Weighted average emphasizing safety (40%), evidence (25%), 
   integration (20%), practicality (15%)

6. **Recommendation Tier**:
   - "Highly Recommended": Final score ≥ 8, safety ≥ 8
   - "Recommended with Caution": Final score ≥ 6, safety ≥ 6
   - "Requires Professional Supervision": Final score ≥ 5, safety < 6
   - "Not Recommended": Final score < 5 OR safety < 4

Provide scores and brief reasoning."""


async def orchestration_scorer_node(state: DebateState) -> dict:
    """
    Score the quality of the debate and final recommendations.
    
    Uses structured output to ensure consistent scoring format.
    """
    logger.info("orchestration_scorer_node started")
    await emit_progress(state, "scoring", "Evaluating recommendation quality")
    
    settings = get_settings()
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    model_name = settings.debate_scoring_model or settings.planner_model
    
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.2,
        timeout=60
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ORCHESTRATION_SCORER_SYSTEM),
        ("human", "Please score this debate according to the criteria.")
    ])
    
    # Format risk map for display
    risk_map = state.get("risk_map", {})
    risk_summary = f"Overall Risk: {risk_map.get('overall_risk_level', 'unknown')}\n"
    risk_summary += f"Safe items: {', '.join(risk_map.get('safe_recommendations', []))}\n"
    risk_summary += f"Flagged items: {', '.join(risk_map.get('flagged_recommendations', []))}\n"
    if risk_map.get("risks"):
        risk_summary += "Specific risks:\n"
        for risk in risk_map["risks"][:5]:  # Limit to top 5
            risk_summary += f"- {risk['herb_or_action']}/{risk['condition']}: {risk['severity']}\n"
    
    try:
        # Try structured output first
        try:
            structured_llm = llm.with_structured_output(DebateScores)
            chain = prompt | structured_llm
            scores: DebateScores = await chain.ainvoke({
                "ayurveda_proposal": state.get("ayurveda_proposal", ""),
                "biomedical_critique": state.get("biomedical_critique", ""),
                "ayurveda_revision": state.get("ayurveda_revision", ""),
                "risk_map": risk_summary,
                "health_conditions": state.get("health_conditions", [])
            })
        except NotImplementedError:
            # Fallback to parsing
            parser = PydanticOutputParser(pydantic_object=DebateScores)
            prompt_with_format = ChatPromptTemplate.from_messages([
                ("system", ORCHESTRATION_SCORER_SYSTEM + "\n\n{format_instructions}"),
                ("human", "Please score this debate according to the criteria.")
            ])
            chain = prompt_with_format | llm | parser
            scores: DebateScores = await chain.ainvoke({
                "ayurveda_proposal": state.get("ayurveda_proposal", ""),
                "biomedical_critique": state.get("biomedical_critique", ""),
                "ayurveda_revision": state.get("ayurveda_revision", ""),
                "risk_map": risk_summary,
                "health_conditions": state.get("health_conditions", []),
                "format_instructions": parser.get_format_instructions()
            })
        
        logger.info("orchestration_scorer_node completed: final_score=%.1f, tier=%s",
                    scores.final_score, scores.recommendation_tier)
        
        return {
            "debate_scores": {
                "evidence_score": scores.evidence_score,
                "safety_score": scores.safety_score,
                "integration_score": scores.integration_score,
                "practicality_score": scores.practicality_score,
                "final_score": scores.final_score,
                "score_reasoning": scores.score_reasoning,
                "recommendation_tier": scores.recommendation_tier
            }
        }
        
    except Exception as e:
        logger.exception("orchestration_scorer_node failed")
        # Fallback to conservative scoring
        risk_level = risk_map.get("overall_risk_level", "moderate")
        safety = 4.0 if risk_level in ["high", "critical"] else 6.0
        
        return {
            "debate_scores": {
                "evidence_score": 5.0,
                "safety_score": safety,
                "integration_score": 5.0,
                "practicality_score": 5.0,
                "final_score": 5.0,
                "score_reasoning": f"Fallback scoring due to error: {str(e)[:50]}",
                "recommendation_tier": "Requires Professional Supervision"
            }
        }


def format_final_response(state: DebateState) -> str:
    """Format the final response combining revision, scores, and risk info."""
    revision = state.get("ayurveda_revision", "")
    scores = state.get("debate_scores", {})
    risk_map = state.get("risk_map", {})
    
    # Build the response
    parts = []
    
    # Main recommendations
    parts.append(revision)
    
    # Risk summary if any risks found
    if risk_map.get("flagged_recommendations"):
        parts.append("\n\n---\n")
        parts.append("⚠️ **Safety Notes:**")
        for herb in risk_map["flagged_recommendations"]:
            parts.append(f"- `{herb}` may have interactions with your conditions - use with caution")
    
    # Score summary
    parts.append("\n\n---\n")
    parts.append(f"📊 **Recommendation Quality:** {scores.get('recommendation_tier', 'Under Review')}")
    parts.append(f"- Evidence: {scores.get('evidence_score', 'N/A')}/10")
    parts.append(f"- Safety: {scores.get('safety_score', 'N/A')}/10")
    parts.append(f"- Overall: {scores.get('final_score', 'N/A')}/10")
    
    return "\n".join(parts)


async def assemble_response_node(state: DebateState) -> dict:
    """
    Assemble the final response from debate components.
    """
    logger.info("assemble_response_node started")
    await emit_progress(state, "assembling", "Preparing final response")
    
    final_response = format_final_response(state)
    
    return {"final_response": final_response}


async def guardrail_node(state: DebateState) -> dict:
    """
    Apply IronDome guardrails to the final response.
    
    Reuses the same guardrails as the main Clinical Council.
    """
    logger.info("guardrail_node started (debate)")
    await emit_progress(state, "guardrail", "Final safety check")
    
    guardrails = get_guardrails()
    response = state.get("final_response", "")
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


# === Graph Construction ===

def create_debate_council() -> StateGraph:
    """
    Build the Multi-Agent Debate workflow.
    
    Flow:
    1. retrieve_context → ayurveda_proposal → biomedical_critique
    2. → ayurveda_revision → risk_mapper → orchestration_scorer
    3. → assemble_response → guardrail → END
    
    This is a linear pipeline where each step builds on previous outputs.
    """
    workflow = StateGraph(DebateState)
    
    # Add all nodes
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("ayurveda_proposal", ayurveda_proposal_node)
    workflow.add_node("biomedical_critique", biomedical_critique_node)
    workflow.add_node("ayurveda_revision", ayurveda_revision_node)
    workflow.add_node("risk_mapper", risk_mapper_node)
    workflow.add_node("orchestration_scorer", orchestration_scorer_node)
    workflow.add_node("assemble_response", assemble_response_node)
    workflow.add_node("guardrail", guardrail_node)
    
    # Entry point
    workflow.set_entry_point("retrieve_context")
    
    # Linear flow
    workflow.add_edge("retrieve_context", "ayurveda_proposal")
    workflow.add_edge("ayurveda_proposal", "biomedical_critique")
    workflow.add_edge("biomedical_critique", "ayurveda_revision")
    workflow.add_edge("ayurveda_revision", "risk_mapper")
    workflow.add_edge("risk_mapper", "orchestration_scorer")
    workflow.add_edge("orchestration_scorer", "assemble_response")
    workflow.add_edge("assemble_response", "guardrail")
    workflow.add_edge("guardrail", END)
    
    return workflow.compile()


# === Public API ===

async def process_debate_query(
    user_id: str,
    query: str,
    dosha_profile: Optional[dict] = None,
    health_conditions: Optional[list[str]] = None,
    messages: Optional[list[BaseMessage]] = None,
    progress_callback: Optional[Callable[[str, Optional[str]], Awaitable[None]]] = None
) -> dict:
    """
    Process a user query through the Multi-Agent Debate protocol.
    
    This is an alternative to the standard Clinical Council that provides
    more rigorous review through structured debate between Ayurvedic
    and Biomedical perspectives.
    
    Args:
        user_id: Unique user identifier
        query: User's question or message
        dosha_profile: Optional Dosha scores (vata, pitta, kapha)
        health_conditions: Known health conditions for safety checks
        messages: Optional conversation history
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict with response, debate components, scores, and safety info
    """
    logger.info("process_debate_query started")
    council = create_debate_council()
    
    initial_state: DebateState = {
        "user_id": user_id,
        "user_query": query,
        "messages": messages or [],
        "dosha_profile": dosha_profile or {"vata": 0.33, "pitta": 0.33, "kapha": 0.34},
        "health_conditions": health_conditions or [],
        "graph_context": "",
        "ayurveda_proposal": "",
        "biomedical_critique": "",
        "ayurveda_revision": "",
        "risk_map": None,
        "debate_scores": None,
        "final_response": "",
        "guardrail_result": None,
        "is_complete": False,
        "progress_callback": progress_callback
    }
    
    try:
        result = await council.ainvoke(initial_state)
    except Exception as e:
        logger.exception("process_debate_query failed")
        raise
    
    logger.info("process_debate_query completed")
    
    guardrail_result = result.get("guardrail_result") or {}
    debate_scores = result.get("debate_scores") or {}
    risk_map = result.get("risk_map") or {}
    
    return {
        "response": result.get("final_response", "Unable to generate response."),
        "mode": "debate",
        
        # Debate components
        "ayurveda_proposal": result.get("ayurveda_proposal", ""),
        "biomedical_critique": result.get("biomedical_critique", ""),
        "ayurveda_revision": result.get("ayurveda_revision", ""),
        
        # Risk assessment
        "risk_map": risk_map,
        "overall_risk_level": risk_map.get("overall_risk_level", "unknown"),
        
        # Scores
        "debate_scores": debate_scores,
        "final_score": debate_scores.get("final_score", 0),
        "recommendation_tier": debate_scores.get("recommendation_tier", "Under Review"),
        
        # Safety
        "guardrail_passed": guardrail_result.get("passed", True),
        "guardrail_violations": guardrail_result.get("violations", []),
    }
