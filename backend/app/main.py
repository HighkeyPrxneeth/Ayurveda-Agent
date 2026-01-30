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
from .services import DoshaCalculator, get_dosha_calculator, PRAKRITI_QUESTIONS
from .agents import generate_treatment_plan, process_query


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

class ChatRequest(BaseModel):
    """Input for the chat interface using the Clinical Council."""
    message: str = Field(..., min_length=1, description="User's message")
    user_id: Optional[str] = Field(None, description="User identifier for context tracking")
    dosha_scores: Optional[dict[str, float]] = Field(None, description="Known Dosha scores")
    health_conditions: list[str] = Field(default_factory=list, description="Known conditions")


class ChatResponse(BaseModel):
    """Response from the Clinical Council."""
    response: str
    route: str  # Which intent was classified
    guardrail_passed: bool
    guardrail_violations: list[dict]
    workers_consulted: int
    disclaimer: str = "This is for educational/wellness purposes only. Not a medical diagnosis."


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
    
    try:
        result = await process_query(
            user_id=user_id,
            query=request.message,
            dosha_profile=dosha_profile,
            health_conditions=request.health_conditions
        )
        
        return ChatResponse(
            response=result["response"],
            route=result["route"],
            guardrail_passed=result["guardrail_passed"],
            guardrail_violations=result["guardrail_violations"],
            workers_consulted=result["workers_consulted"]
        )
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

    async def run_pipeline():
        try:
            result = await process_query(
                user_id=user_id,
                query=request.message,
                dosha_profile=dosha_profile,
                health_conditions=request.health_conditions,
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


# === Startup Event ===

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    settings = get_settings()
    print(f"🌿 {settings.app_name} API starting...")
    print(f"   Architecture: Hierarchical Clinical Council")
    print(f"   Planner Model: {settings.planner_model}")
    print(f"   Executor Model: {settings.executor_model}")
    print(f"   Endpoints:")
    print(f"     - POST /api/v1/chat (Clinical Council)")
    print(f"     - POST /api/v1/generate-plan (Legacy PER)")
    
    if not settings.openai_api_key:
        print("   ⚠️  OpenAI API key not set - agent endpoints will fail")
    if not settings.groq_api_key:
        print("   ℹ️  Groq API key not set - using OpenAI fallback for fast responder")
