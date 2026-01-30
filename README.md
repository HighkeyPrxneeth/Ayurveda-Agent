# 🌿 Ayush Habba

**Hybrid Neuro-Symbolic AI for Personalized Ayurvedic Treatment**

A full-stack application combining deterministic Ayurvedic rules (Symbolic AI) with modern LLM-powered agents (Neural AI) for safe, personalized wellness recommendations.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                          │
│  ┌─────────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │ DoshaForm   │  │ TreatmentDash   │  │  ChatInterface    │   │
│  └─────────────┘  └─────────────────┘  └───────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   API Layer (main.py)                        ││
│  │  /assess-dosha  │  /assess-vitals  │  /generate-plan        ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐    ┌─────────────────┐   ┌───────────────┐    │
│  │ SYMBOLIC AI │    │  NEURO-SYMBOLIC │   │    TOOLS      │    │
│  │ DoshaCalc   │◄───│  PER Agent      │──►│ Contraind.    │    │
│  │ (Rules)     │    │  (LangGraph)    │   │ Diet Lookup   │    │
│  └─────────────┘    └─────────────────┘   └───────────────┘    │
│                              │                                   │
│                  ┌───────────┴───────────┐                      │
│                  ▼                       ▼                      │
│         ┌─────────────┐         ┌─────────────┐                 │
│         │  PLANNER    │         │  EXECUTOR   │                 │
│         │  GPT-4o     │         │  Llama-3-70B│                 │
│         │  (OpenAI)   │         │  (Groq)     │                 │
│         └─────────────┘         └─────────────┘                 │
└──────────────────────────────────────────────────────────────────┘
```

### Key Components

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14 + Tailwind | SSR, Responsive UI, Dosha visualization |
| **API** | FastAPI | High-performance async endpoints |
| **Symbolic AI** | Python (DoshaCalculator) | Deterministic Prakriti scoring |
| **Neural AI** | LangGraph + LangChain | Planner-Executor-Reviewer agents |
| **Planner LLM** | GPT-4o (OpenAI) | Complex reasoning, plan creation |
| **Executor LLM** | Llama-3.3-70B (Groq) | Cost-effective tool execution |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (required for agent)
- Groq API key (optional, for cost optimization)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your API keys

# (Optional) LM Studio local prototyping
# - Start LM Studio server (OpenAI compatible)
# - Set OPENAI_BASE_URL=http://localhost:1234/v1
# - Set OPENAI_API_KEY to any non-empty value if your server requires it

# Run server
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **Backend ReDoc**: http://localhost:8000/redoc

---

## API Endpoints

### Symbolic AI (Deterministic)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/questions` | GET | Get Prakriti assessment questions |
| `/api/v1/assess-dosha` | POST | Calculate Prakriti from answers |
| `/api/v1/assess-vitals` | POST | Infer Dosha from physiological vitals |

### Neuro-Symbolic Agent

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/generate-plan` | POST | Generate personalized treatment plan |

---

## Project Structure

```
Ayush Habba/
├── backend/
│   ├── app/
│   │   ├── agents/           # LangGraph PER workflow
│   │   │   ├── per_workflow.py
│   │   │   └── tools.py
│   │   ├── models/           # Pydantic data models
│   │   │   ├── dosha.py
│   │   │   └── treatment.py
│   │   ├── services/         # Business logic
│   │   │   ├── dosha_calculator.py
│   │   │   └── question_bank.py
│   │   ├── config.py         # Settings from env
│   │   └── main.py           # FastAPI app
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   │   ├── page.tsx      # Home
│   │   │   ├── assess/       # Assessment flow
│   │   │   └── dashboard/    # Main dashboard
│   │   ├── components/       # React components
│   │   │   ├── DoshaBars.tsx
│   │   │   ├── DoshaForm.tsx
│   │   │   └── ChatInterface.tsx
│   │   └── lib/              # Utilities & API client
│   │       ├── api.ts
│   │       └── utils.ts
│   ├── package.json
│   └── tailwind.config.ts
│
└── README.md
```

---

## Usage Examples

### 1. Prakriti Assessment

```python
# Assess Dosha from questionnaire
POST /api/v1/assess-dosha
{
  "answers": [
    {"question_id": "PHY_001", "answer_value": 4},
    {"question_id": "PHY_002", "answer_value": 2},
    // ... more answers
  ]
}

# Response
{
  "scores": {"vata": 0.45, "pitta": 0.35, "kapha": 0.20},
  "dominant_dosha": "Vata",
  "constitution_type": "Vata-Pitta"
}
```

### 2. Treatment Plan Generation

```python
POST /api/v1/generate-plan
{
  "query": "How should I balance my high Pitta with diet?",
  "dosha_scores": {"vata": 0.25, "pitta": 0.50, "kapha": 0.25},
  "health_conditions": ["hyperthyroidism"]
}

# Response includes personalized recommendations with:
# - Contraindication checks
# - Source citations
# - Safety notes
```

---

## Cost Optimization

The architecture implements **70-90% cost reduction** by using:

| Component | Model | Cost |
|-----------|-------|------|
| Planner | GPT-4o | ~$2.50/1M tokens |
| Executor | Llama-3.3-70B (Groq) | ~$0.60/1M tokens |

If Groq API key is not provided, the system falls back to `gpt-4o-mini`.

## Local LLM Prototyping (LM Studio)

1. Launch LM Studio and start the OpenAI-compatible server.
2. Set the environment variable in [backend/.env](backend/.env):
  - OPENAI_BASE_URL=http://localhost:1234/v1
3. Use a model name that LM Studio exposes (e.g., `gpt-4o` can be changed to your local model name).

Note: If LM Studio requires an API key, set `OPENAI_API_KEY` to any non-empty string.

---

## Safety & Compliance

- ✅ **Contraindication Database**: Hard-coded safety checks for herb-condition interactions
- ✅ **Reviewer Agent**: All recommendations pass through safety validation
- ✅ **Source Traceability**: Every recommendation cites its source text
- ✅ **Legal Disclaimer**: Application clearly states "wellness/educational" purpose

⚠️ **Important**: This is NOT a medical diagnostic tool. Always consult qualified practitioners.

---

## Development

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Adding New Questions

Edit `backend/app/services/question_bank.py` to add new Prakriti questions.

### Adding New Tools

Add new tool functions in `backend/app/agents/tools.py` and include them in the `ayurveda_tools` list.

---

## License

This project is for educational purposes. Ensure compliance with local healthcare regulations before deployment.
