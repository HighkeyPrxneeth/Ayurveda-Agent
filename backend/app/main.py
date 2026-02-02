"""
Ayush Habba - FastAPI Backend Entry Point

Exposes APIs for:
- Prakriti Assessment (Deterministic Symbolic AI)
- Treatment Planning (Neuro-Symbolic Agentic AI)
- Chat Interface (Hierarchical Clinical Council)
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, AsyncIterator
import uuid
import logging
import asyncio
import json

from .config import get_settings, Settings
from .models import DoshaScore, PrakritiAssessment, TreatmentPlan
from .services import DoshaCalculator, get_dosha_calculator, PRAKRITI_QUESTIONS, get_response_cache, get_dosha_tracker
from .agents import generate_treatment_plan, process_query, process_debate_query


# === Application Setup ===

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ayush Habba API",
    description="Hybrid Neuro-Symbolic AI for Personalized Ayurvedic Wellness",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Request/Response Models ===

class VitalsInput(BaseModel):
    """Input model for vitals-based Dosha assessment."""
    heart_rate: Optional[float] = Field(None, ge=40, le=200, description="BPM")
    hrv: Optional[float] = Field(None, ge=5, le=300, description="HRV in ms")
    skin_temp: Optional[float] = Field(None, ge=30, le=42, description="°C")
    respiration_rate: Optional[float] = Field(None, ge=8, le=40, description="Breaths/min")


class TreatmentRequest(BaseModel):
    """Input for treatment plan generation."""
    query: str = Field(..., min_length=5, description="User's wellness question")
    dosha_scores: Optional[dict[str, float]] = Field(None, description="Known Dosha scores")
    health_conditions: list[str] = Field(default_factory=list, description="Known conditions")


class QuestionResponse(BaseModel):
    """A single question for the frontend."""
    question_id: str
    question_text: str
    category: str
    weight: float


class AssessmentResponse(BaseModel):
    """Response for Dosha assessment."""
    scores: DoshaScore
    dominant_dosha: str
    constitution_type: str


class TreatmentResponse(BaseModel):
    """Response for treatment plan."""
    response: str
    safety_notes: list[str]
    is_safe: bool
    steps_executed: int
    disclaimer: str = "This is for educational/wellness purposes only. Not a medical diagnosis."


# === NEW: Chat Interface Models (Clinical Council) ===

class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Input for the chat interface using the Clinical Council."""
    message: str = Field(..., min_length=1, description="User's message")
    user_id: Optional[str] = Field(None, description="User identifier for context tracking")
    dosha_scores: Optional[dict[str, float]] = Field(None, description="Known Dosha scores")
    health_conditions: list[str] = Field(default_factory=list, description="Known conditions")
    conversation_history: list[ConversationMessage] = Field(default_factory=list, description="Previous conversation messages")


class ChatResponse(BaseModel):
    """Response from the Clinical Council."""
    response: str
    route: str  # Which intent was classified
    guardrail_passed: bool
    guardrail_violations: list[dict]
    workers_consulted: int
    disclaimer: str = "This is for educational/wellness purposes only. Not a medical diagnosis."


class DebateRequest(BaseModel):
    """Input for the multi-agent debate protocol."""
    message: str = Field(..., min_length=1, description="User's wellness question")
    user_id: Optional[str] = Field(None, description="User identifier for context tracking")
    dosha_scores: Optional[dict[str, float]] = Field(None, description="Known Dosha scores")
    health_conditions: list[str] = Field(default_factory=list, description="Known health conditions - critical for biomedical review")
    conversation_history: list[ConversationMessage] = Field(default_factory=list, description="Previous conversation messages")


class DebateResponse(BaseModel):
    """Response from the Multi-Agent Debate Protocol."""
    response: str
    mode: str = "debate"
    
    # Debate components (for transparency)
    ayurveda_proposal: str
    biomedical_critique: str
    ayurveda_revision: str
    
    # Risk assessment
    risk_map: dict
    overall_risk_level: str
    
    # Scores
    debate_scores: dict
    final_score: float
    recommendation_tier: str
    
    # Safety
    guardrail_passed: bool
    guardrail_violations: list[dict]
    
    disclaimer: str = "This is for educational/wellness purposes only. Not a medical diagnosis. The debate protocol provides multiple perspectives but does not replace professional medical advice."


# === Health Check ===

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "ayush-habba-api"}


# === Dosha Assessment Endpoints (Symbolic AI) ===

@app.get("/api/v1/questions", response_model=list[QuestionResponse])
async def get_prakriti_questions():
    """
    Get all Prakriti assessment questions.
    
    Returns the C-DAC Ayusoft compatible questionnaire.
    Frontend should display these and collect answers on 1-5 scale.
    """
    return [
        QuestionResponse(
            question_id=q.question_id,
            question_text=q.question_text,
            category=q.category,
            weight=q.weight
        )
        for q in PRAKRITI_QUESTIONS
    ]


@app.post("/api/v1/assess-dosha", response_model=AssessmentResponse)
async def assess_dosha_from_questionnaire(
    assessment: PrakritiAssessment,
    calculator: DoshaCalculator = Depends(get_dosha_calculator)
):
    """
    Calculate Prakriti (constitution) from questionnaire answers.
    
    This is a deterministic calculation using rule-based scoring.
    No ML/AI involved - clinically validated methodology.
    """
    scores = calculator.calculate_prakriti(assessment.answers)
    
    return AssessmentResponse(
        scores=scores,
        dominant_dosha=scores.dominant_dosha.value,
        constitution_type=scores.constitution_type
    )


@app.post("/api/v1/assess-vitals", response_model=AssessmentResponse)
async def assess_dosha_from_vitals(
    vitals: VitalsInput,
    calculator: DoshaCalculator = Depends(get_dosha_calculator)
):
    """
    Infer current Dosha state (Vikriti) from physiological vitals.
    
    Maps heart rate, HRV, skin temperature, respiration to Dosha tendencies.
    Useful for wearable device integration.
    """
    scores = calculator.map_vitals_to_dosha(
        heart_rate=vitals.heart_rate,
        hrv=vitals.hrv,
        skin_temp=vitals.skin_temp,
        respiration_rate=vitals.respiration_rate
    )
    
    return AssessmentResponse(
        scores=scores,
        dominant_dosha=scores.dominant_dosha.value,
        constitution_type=scores.constitution_type
    )


# === Treatment Planning Endpoint (Neuro-Symbolic Agent) ===

@app.post("/api/v1/generate-plan", response_model=TreatmentResponse)
async def generate_treatment(request: TreatmentRequest):
    """
    Generate personalized treatment recommendations using the PER Agent.
    
    This endpoint uses the Planner-Executor-Reviewer agentic workflow:
    1. Planner (GPT-4o) creates a step-by-step plan
    2. Executor (Llama-3-70B) runs each step using Ayurvedic tools
    3. Reviewer validates safety and contraindications
    
    Requires API keys configured in environment variables.
    """
    settings = get_settings()
    
    if not settings.openai_api_key and not settings.openai_base_url:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL for LM Studio."
        )
    
    # Use provided scores or default balanced
    dosha_context = request.dosha_scores or {
        "vata": 0.33,
        "pitta": 0.33,
        "kapha": 0.34
    }
    
    try:
        result = await generate_treatment_plan(
            user_query=request.query,
            dosha_context=dosha_context,
            health_conditions=request.health_conditions
        )
        
        return TreatmentResponse(
            response=result["response"],
            safety_notes=result["safety_notes"],
            is_safe=result["is_safe"],
            steps_executed=result["steps_executed"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating treatment plan: {str(e)}"
        )


# === NEW: Chat Endpoint (Hierarchical Clinical Council) ===

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint using the Hierarchical Clinical Council architecture.

    This is the improved agentic system that replaces the PER workflow:

    **Architecture:**
    1. Semantic Router classifies intent (<200ms latency)
    2. Simple queries → Fast Responder (Llama-3-8B)
    3. Complex queries → Supervisor → Specialist Workers → Aggregator
    4. All outputs → Iron Dome Guardrails (deterministic safety)

    **Specialist Workers:**
    - Ayurveda Specialist: Dosha analysis, Prakriti/Vikriti assessment
    - Pharmacist: Herb safety, drug interactions, contraindications
    - Diagnostics: Symptom pattern recognition, wellness mapping
    - Diet Coach: Dietary advice, meal planning, lifestyle routines

    **Safety:**
    - Content filtering for prompt injection
    - Deterministic guardrails (no LLM-based reviewer)
    - Emergency detection and instant handoff

    **Performance:**
    - Response caching for identical queries with same context
    """
    settings = get_settings()

    if not settings.openai_api_key and not settings.openai_base_url:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL."
        )

    # Generate user_id if not provided
    user_id = request.user_id or str(uuid.uuid4())

    # Use provided scores or default balanced
    dosha_profile = request.dosha_scores or {
        "vata": 0.33,
        "pitta": 0.33,
        "kapha": 0.34
    }

    # Build cache context (exclude conversation history for simpler caching)
    cache_context = {
        "dosha_scores": dosha_profile,
        "health_conditions": sorted(request.health_conditions) if request.health_conditions else []
    }

    # Check cache first (only for queries without conversation history)
    cache = get_response_cache()
    if not request.conversation_history:
        cached_result = cache.get(request.message, cache_context)
        if cached_result:
            logger.info("Cache hit for query: %s", request.message[:50])
            return ChatResponse(**cached_result)

    # Convert conversation history to LangChain messages
    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for msg in request.conversation_history:
        if msg.role == 'user':
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == 'assistant':
            messages.append(AIMessage(content=msg.content))

    try:
        result = await process_query(
            user_id=user_id,
            query=request.message,
            dosha_profile=dosha_profile,
            health_conditions=request.health_conditions,
            messages=messages
        )

        response_data = {
            "response": result["response"],
            "route": result["route"],
            "guardrail_passed": result["guardrail_passed"],
            "guardrail_violations": result["guardrail_violations"],
            "workers_consulted": result["workers_consulted"],
            "disclaimer": "This is for educational/wellness purposes only. Not a medical diagnosis."
        }

        # Cache the result (only for queries without conversation history)
        if not request.conversation_history:
            cache.set(request.message, response_data, cache_context)

        return ChatResponse(**response_data)
    except Exception as e:
        logger.exception("Error processing chat request")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat: {str(e)}"
        )


def chunk_text(text: str, size: int = 24):
    for start in range(0, len(text), size):
        yield text[start:start + size]


@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint using SSE.

    Emits events:
    - status: { stage, detail }
    - delta: { text }
    - done: ChatResponse
    - error: { message }
    """
    settings = get_settings()

    if not settings.openai_api_key and not settings.openai_base_url:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL."
        )

    user_id = request.user_id or str(uuid.uuid4())
    dosha_profile = request.dosha_scores or {
        "vata": 0.33,
        "pitta": 0.33,
        "kapha": 0.34
    }

    queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

    async def progress_callback(stage: str, detail: Optional[str] = None):
        await queue.put({"event": "status", "data": {"stage": stage, "detail": detail}})

    # Convert conversation history to LangChain messages
    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for msg in request.conversation_history:
        if msg.role == 'user':
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == 'assistant':
            messages.append(AIMessage(content=msg.content))

    async def run_pipeline():
        try:
            result = await process_query(
                user_id=user_id,
                query=request.message,
                dosha_profile=dosha_profile,
                health_conditions=request.health_conditions,
                messages=messages,
                progress_callback=progress_callback
            )

            await queue.put({"event": "status", "data": {"stage": "response", "detail": None}})
            response_text = result.get("response", "")
            for chunk in chunk_text(response_text):
                await queue.put({"event": "delta", "data": {"text": chunk}})
                await asyncio.sleep(0)

            await queue.put({"event": "done", "data": result})
        except Exception as e:
            logger.exception("Error processing chat stream")
            await queue.put({"event": "error", "data": {"message": str(e)}})
        finally:
            await queue.put(None)

    asyncio.create_task(run_pipeline())

    async def event_generator() -> AsyncIterator[str]:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


# === Multi-Agent Debate Protocol Endpoints ===

@app.post("/api/v1/chat/debate", response_model=DebateResponse)
async def chat_debate(request: DebateRequest):
    """
    Multi-Agent Debate Protocol endpoint.
    
    This endpoint provides a more rigorous review process where:
    
    **Debate Flow:**
    1. **Ayurveda Expert** (with RAG): Generates initial recommendations
       based on Dosha profile, health history, and Ayurvedic principles
    2. **Biomedical Expert** (no RAG): Critiques from evidence-based perspective,
       flags safety concerns and unsupported claims
    3. **Ayurveda Revision**: Integrates valid biomedical concerns while
       maintaining appropriate traditional practices
    4. **Risk Mapper**: Deterministic contraindication checks against known conditions
    5. **Orchestration Scorer**: Scores the debate quality on evidence, safety,
       integration, and practicality
    
    **Key Differences from /api/v1/chat:**
    - More thorough review process (takes longer)
    - Provides transparency into the debate (shows all perspectives)
    - Includes quantitative scoring
    - Better for complex health queries or users with multiple conditions
    
    **When to Use:**
    - User has multiple health conditions
    - Query involves herbs or supplements
    - User wants to understand both Ayurvedic and biomedical perspectives
    - Higher-stakes wellness decisions
    """
    settings = get_settings()
    
    if not settings.openai_api_key and not settings.openai_base_url:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL."
        )
    
    user_id = request.user_id or str(uuid.uuid4())
    dosha_profile = request.dosha_scores or {
        "vata": 0.33,
        "pitta": 0.33,
        "kapha": 0.34
    }
    
    # Convert conversation history
    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for msg in request.conversation_history:
        if msg.role == 'user':
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == 'assistant':
            messages.append(AIMessage(content=msg.content))
    
    try:
        result = await process_debate_query(
            user_id=user_id,
            query=request.message,
            dosha_profile=dosha_profile,
            health_conditions=request.health_conditions,
            messages=messages
        )
        
        return DebateResponse(
            response=result["response"],
            mode=result["mode"],
            ayurveda_proposal=result["ayurveda_proposal"],
            biomedical_critique=result["biomedical_critique"],
            ayurveda_revision=result["ayurveda_revision"],
            risk_map=result["risk_map"],
            overall_risk_level=result["overall_risk_level"],
            debate_scores=result["debate_scores"],
            final_score=result["final_score"],
            recommendation_tier=result["recommendation_tier"],
            guardrail_passed=result["guardrail_passed"],
            guardrail_violations=result["guardrail_violations"]
        )
        
    except Exception as e:
        logger.exception("Error processing debate request")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing debate: {str(e)}"
        )


@app.post("/api/v1/chat/debate/stream")
async def chat_debate_stream(request: DebateRequest):
    """
    Streaming version of the Multi-Agent Debate Protocol.
    
    Emits SSE events for each stage of the debate:
    - status: { stage: "context" | "ayurveda_proposal" | "biomedical_critique" | 
                "ayurveda_revision" | "risk_mapping" | "scoring" | "assembling" | "guardrail",
                detail: optional string }
    - delta: { text: chunk } - for final response streaming
    - done: DebateResponse - complete result
    - error: { message: string }
    """
    settings = get_settings()
    
    if not settings.openai_api_key and not settings.openai_base_url:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL."
        )
    
    user_id = request.user_id or str(uuid.uuid4())
    dosha_profile = request.dosha_scores or {
        "vata": 0.33,
        "pitta": 0.33,
        "kapha": 0.34
    }
    
    queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
    
    async def progress_callback(stage: str, detail: Optional[str] = None):
        await queue.put({"event": "status", "data": {"stage": stage, "detail": detail}})
    
    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for msg in request.conversation_history:
        if msg.role == 'user':
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == 'assistant':
            messages.append(AIMessage(content=msg.content))
    
    async def run_debate_pipeline():
        try:
            result = await process_debate_query(
                user_id=user_id,
                query=request.message,
                dosha_profile=dosha_profile,
                health_conditions=request.health_conditions,
                messages=messages,
                progress_callback=progress_callback
            )
            
            await queue.put({"event": "status", "data": {"stage": "response", "detail": None}})
            response_text = result.get("response", "")
            for chunk in chunk_text(response_text):
                await queue.put({"event": "delta", "data": {"text": chunk}})
                await asyncio.sleep(0)
            
            await queue.put({"event": "done", "data": result})
        except Exception as e:
            logger.exception("Error processing debate stream")
            await queue.put({"event": "error", "data": {"message": str(e)}})
        finally:
            await queue.put(None)
    
    asyncio.create_task(run_debate_pipeline())
    
    async def event_generator() -> AsyncIterator[str]:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
    
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


# === Cache Management Endpoints ===

@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """Get cache statistics for monitoring performance."""
    cache = get_response_cache()
    return cache.get_stats()


@app.delete("/api/v1/cache")
async def clear_cache():
    """Clear all cached responses."""
    cache = get_response_cache()
    count = cache.clear()
    return {"cleared": count, "message": f"Cleared {count} cached entries"}


# === Dosha Trend Tracking Endpoints ===

class DoshaTrackRequest(BaseModel):
    """Request to track a Dosha assessment."""
    user_id: str = Field(..., min_length=1, description="User identifier")
    vata: float = Field(..., ge=0, le=1, description="Vata score (0-1)")
    pitta: float = Field(..., ge=0, le=1, description="Pitta score (0-1)")
    kapha: float = Field(..., ge=0, le=1, description="Kapha score (0-1)")
    dominant_dosha: str = Field(..., description="Dominant Dosha type")
    constitution_type: str = Field(..., description="Constitution type (e.g., Vata-Pitta)")
    source: str = Field(default="questionnaire", description="Assessment source")


class DoshaHistoryEntry(BaseModel):
    """A single Dosha history entry."""
    timestamp: str
    vata: float
    pitta: float
    kapha: float
    dominant_dosha: str
    constitution_type: str
    source: str


class DoshaTrendResponse(BaseModel):
    """Response containing Dosha trend data for visualization."""
    labels: list[str]
    vata: list[float]
    pitta: list[float]
    kapha: list[float]
    dominant: list[str]
    count: int


@app.post("/api/v1/dosha/track", response_model=DoshaHistoryEntry)
async def track_dosha_assessment(request: DoshaTrackRequest):
    """
    Track a Dosha assessment for trend analysis.

    Stores the assessment with timestamp for historical tracking.
    Use this endpoint after each Dosha assessment to build trend data.
    """
    tracker = get_dosha_tracker()
    entry = tracker.track_assessment(
        user_id=request.user_id,
        vata=request.vata,
        pitta=request.pitta,
        kapha=request.kapha,
        dominant_dosha=request.dominant_dosha,
        constitution_type=request.constitution_type,
        source=request.source
    )
    return DoshaHistoryEntry(**entry.to_dict())


@app.get("/api/v1/dosha/history/{user_id}", response_model=list[DoshaHistoryEntry])
async def get_dosha_history(user_id: str, limit: int = 30):
    """
    Get Dosha assessment history for a user.

    Returns the most recent assessments, ordered newest first.
    """
    tracker = get_dosha_tracker()
    entries = tracker.get_history(user_id, limit=limit)
    return [DoshaHistoryEntry(**e.to_dict()) for e in entries]


@app.get("/api/v1/dosha/trend/{user_id}", response_model=DoshaTrendResponse)
async def get_dosha_trend(user_id: str, limit: int = 30):
    """
    Get Dosha trend data formatted for chart visualization.

    Returns data suitable for line/area charts showing Dosha balance over time.
    """
    tracker = get_dosha_tracker()
    trend_data = tracker.get_trend_data(user_id, limit=limit)
    return DoshaTrendResponse(**trend_data)


@app.delete("/api/v1/dosha/history/{user_id}")
async def clear_dosha_history(user_id: str):
    """Clear all Dosha history for a user."""
    tracker = get_dosha_tracker()
    count = tracker.clear_history(user_id)
    return {"cleared": count, "message": f"Cleared {count} history entries for user {user_id}"}


# === Startup Event ===

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    settings = get_settings()
    print(f"🌿 {settings.app_name} API starting...")
    print(f"   Architecture: Hierarchical Clinical Council + Debate Protocol")
    print(f"   Planner Model: {settings.planner_model}")
    print(f"   Executor Model: {settings.executor_model}")
    print("   Task Models:")
    print(f"     - Council Supervisor: {settings.council_supervisor_model or settings.planner_model}")
    print(f"     - Council Aggregator: {settings.council_aggregator_model or settings.executor_model}")
    print(f"     - Workers Specialist: {settings.workers_specialist_model or settings.planner_model}")
    print(f"     - Workers Fast (Groq): {settings.workers_fast_model or 'meta-llama/llama-4-scout-17b-16e-instruct'}")
    print(f"     - PER Planner: {settings.per_planner_model or settings.planner_model}")
    print(f"     - PER Executor: {settings.per_executor_model or settings.executor_model}")
    print(f"     - PER Synthesizer: {settings.per_synthesizer_model or settings.planner_model}")
    print(f"     - PER Reviewer: {settings.per_reviewer_model or settings.planner_model}")
    print(f"     - Debate Revision: {settings.debate_revision_model or settings.planner_model}")
    print(f"     - Debate Scoring: {settings.debate_scoring_model or settings.planner_model}")
    print(f"   Endpoints:")
    print(f"     - POST /api/v1/chat (Clinical Council)")
    print(f"     - POST /api/v1/chat/debate (Multi-Agent Debate)")
    print(f"     - POST /api/v1/generate-plan (Legacy PER)")
    print(f"     - GET/DELETE /api/v1/cache/stats (Cache Management)")
    print(f"     - POST/GET/DELETE /api/v1/dosha/* (Dosha Trend Tracking)")

    if not settings.openai_api_key:
        print("   ⚠️  OpenAI API key not set - agent endpoints will fail")
    if not settings.groq_api_key:
        print("   ℹ️  Groq API key not set - using OpenAI fallback for fast responder")
