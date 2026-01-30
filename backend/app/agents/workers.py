"""
Specialized Worker Agents - The Clinical Specialists

Each worker agent is a specialized sub-graph with its own tools and prompts.
Workers handle specific domains:
- AyurvedaSpecialist: Dosha analysis, Prakriti/Vikriti assessment
- DiagnosticsAgent: Symptom analysis and wellness mapping
- PharmacistAgent: Herb safety, drug interactions, contraindications
- DietCoach: Diet and lifestyle recommendations

Workers return control to the Supervisor after completing their task.
"""

import logging
from typing import Annotated, TypedDict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

from ..config import get_settings
from .tools import ayurveda_tools, check_contraindication, get_dosha_diet_recommendations


logger = logging.getLogger(__name__)


# === Shared State ===

class WorkerState(TypedDict):
    """State passed to worker agents."""
    messages: list[BaseMessage]
    user_query: str
    dosha_profile: dict  # Prakriti/Vikriti scores
    health_conditions: list[str]
    context_from_graph: Optional[str]  # GraphRAG retrieved context
    worker_output: str
    needs_followup: bool


# === LLM Factory ===

def get_fast_llm():
    """Cost-effective model for simple responses (Llama-3-8B via Groq)."""
    settings = get_settings()
    logger.debug("Initializing fast LLM")
    if settings.groq_api_key:
        logger.info("Using Groq fast LLM")
        return ChatGroq(
            model="meta-llama/llama-4-scout-17b-16e-instruct",  # Fast 8B model
            api_key=settings.groq_api_key,
            temperature=0.3,
            timeout=30
        )
    # Fallback to OpenAI
    logger.info("Using OpenAI fast LLM fallback")
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.3,
        timeout=30
    )


def get_specialist_llm():
    """High-quality model for specialist reasoning."""
    settings = get_settings()
    logger.debug("Initializing specialist LLM")
    api_key = settings.openai_api_key or ("lm-studio" if settings.openai_base_url else "")
    return ChatOpenAI(
        model=settings.planner_model,
        api_key=api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.4,
        timeout=60
    )


# === Worker Agent: Fast Responder ===

FAST_RESPONDER_SYSTEM = """You are a friendly Ayurvedic wellness assistant.
Answer simple questions about Ayurveda warmly and concisely.

Keep responses under 150 words for simple queries.
Use traditional terminology but explain it clearly.
End with a gentle wellness tip when appropriate.

Do NOT:
- Make medical diagnoses
- Recommend specific herb dosages
- Claim to cure diseases
"""


async def fast_responder(query: str, messages: list[BaseMessage] = None) -> str:
    """
    Handle simple queries with a fast, lightweight response.
    
    Used for greetings, basic definitions, and simple questions.
    """
    logger.info("Fast responder invoked")
    llm = get_fast_llm()
    
    # Build conversation context
    conversation_context = ""
    if messages:
        recent_messages = messages[-6:]  # Last 3 exchanges
        history_parts = []
        for msg in recent_messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            history_parts.append(f"{role}: {msg.content[:200]}")
        if history_parts:
            conversation_context = "\n\nRecent conversation:\n" + "\n".join(history_parts)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", FAST_RESPONDER_SYSTEM + conversation_context),
        ("human", "{query}")
    ])
    
    chain = prompt | llm
    logger.debug("Fast responder executing LLM chain")
    response = await chain.ainvoke({"query": query})
    logger.info("Fast responder completed")
    return response.content


# === Worker Agent: Ayurveda Specialist ===

AYURVEDA_SPECIALIST_SYSTEM = """You are a senior Ayurvedic Vaidya (physician) specializing in Prakriti analysis.

Your expertise includes:
- Interpreting Dosha assessments (Prakriti = constitution, Vikriti = current state)
- Understanding how Dosha imbalances manifest as symptoms
- Recommending lifestyle adjustments based on Dosha type
- Explaining Ayurvedic concepts using clear, accessible language

CURRENT USER'S PROFILE:
- Dosha Scores: {dosha_profile}
- Known Health Conditions: {health_conditions}

CONVERSATION HISTORY:
{conversation_history}

CONTEXT FROM PREVIOUS SESSIONS:
{context_from_graph}

GUIDELINES:
1. Always reference the user's specific Dosha profile in your advice
2. Use classical Ayurvedic texts as your knowledge base (Charaka Samhita, Ashtanga Hridaya)
3. Explain the "why" behind recommendations using Dosha theory
4. If vitals are provided, interpret them through the lens of current Vikriti
5. Never claim to diagnose diseases - frame as "imbalance patterns"
6. Reference earlier parts of the conversation when relevant

Response format:
- Start with a brief acknowledgment of their profile
- Provide clear, actionable guidance
- Include the Dosha logic behind your suggestions
- End with one specific recommendation they can implement today
"""


class AyurvedaSpecialist:
    """
    Specialist worker for Prakriti/Vikriti analysis and Dosha-based guidance.
    
    This agent has access to:
    - assess_dosha_from_answers
    - assess_dosha_from_vitals
    - get_dosha_diet_recommendations
    """
    
    def __init__(self):
        logger.debug("Initializing AyurvedaSpecialist")
        self.llm = get_specialist_llm()
        self.tools = [
            t for t in ayurveda_tools 
            if t.name in ["assess_dosha_from_answers", "assess_dosha_from_vitals", 
                         "get_dosha_diet_recommendations"]
        ]
        logger.debug("AyurvedaSpecialist tools: %s", [t.name for t in self.tools])
    
    async def process(self, state: WorkerState) -> dict:
        """
        Process Dosha-related queries.
        
        Returns updated state with worker_output.
        """
        logger.info("AyurvedaSpecialist processing started")
        # Build context string
        context = state.get("context_from_graph") or "No previous session history."
        
        # Build conversation history
        messages = state.get("messages", [])
        conversation_history = "No prior messages in this conversation."
        if messages:
            history_parts = []
            for msg in messages[-10:]:  # Last 5 exchanges
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                history_parts.append(f"{role}: {content}")
            if history_parts:
                conversation_history = "\n".join(history_parts)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", AYURVEDA_SPECIALIST_SYSTEM),
            ("human", "{query}")
        ])
        
        # Bind tools for ReAct-style reasoning
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        chain = prompt | llm_with_tools
        
        try:
            logger.debug("AyurvedaSpecialist invoking LLM chain")
            response = await chain.ainvoke({
                "dosha_profile": state.get("dosha_profile", {}),
                "health_conditions": state.get("health_conditions", []),
                "context_from_graph": context,
                "conversation_history": conversation_history,
                "query": state["user_query"]
            })
            
            # Process any tool calls
            result_parts = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    logger.debug("AyurvedaSpecialist tool call: %s args=%s", tool_name, tool_args)
                    
                    for tool in self.tools:
                        if tool.name == tool_name:
                            tool_result = tool.invoke(tool_args)
                            logger.debug("AyurvedaSpecialist tool result: %s", tool_name)
                            result_parts.append(f"**{tool_name}:** {tool_result}")
                            break
            
            # Combine tool results with LLM response
            output = response.content or ""
            if result_parts:
                output = "\n\n".join(result_parts) + "\n\n" + output
            
            logger.info("AyurvedaSpecialist processing completed")
            return {
                "worker_output": output,
                "needs_followup": False
            }
            
        except Exception as e:
            logger.exception("AyurvedaSpecialist processing failed")
            return {
                "worker_output": f"I encountered an issue analyzing your Dosha profile. Error: {str(e)}",
                "needs_followup": True
            }


# === Worker Agent: Pharmacist (Drug Interaction Checker) ===

PHARMACIST_SYSTEM = """You are an Ayurvedic Pharmacist (Dravyaguna expert) specializing in herb safety.

Your expertise includes:
- Contraindications of Ayurvedic herbs with conditions and medications
- Drug-herb interactions
- Dosage considerations based on constitution
- Safe use during pregnancy, lactation, and in children

USER'S PROFILE:
- Known Health Conditions: {health_conditions}
- Dosha Profile: {dosha_profile}

CONVERSATION HISTORY:
{conversation_history}

STRICT SAFETY RULES:
1. ALWAYS check contraindications before recommending ANY herb
2. If in doubt, recommend consulting a practitioner
3. Never recommend herbs during pregnancy without explicit safety data
4. Flag any potential interaction with common medications
5. Cite sources for contraindication data (Bhavaprakasha, API guidelines)
6. Reference earlier parts of the conversation when relevant

FOR EACH HERB MENTIONED:
- State its primary actions (Rasa, Guna, Virya, Vipaka)
- List known contraindications
- Specify any diet/lifestyle restrictions with the herb
- Recommend safe alternatives if contraindicated
"""


class PharmacistAgent:
    """
    Specialist worker for herb safety and drug interaction checking.
    
    This agent has access to:
    - check_contraindication
    """
    
    def __init__(self):
        logger.debug("Initializing PharmacistAgent")
        self.llm = get_specialist_llm()
        self.tools = [check_contraindication]
        logger.debug("PharmacistAgent tools: %s", [t.name for t in self.tools])
    
    async def process(self, state: WorkerState) -> dict:
        """
        Process herb safety queries.
        
        Always errs on the side of caution.
        """
        logger.info("PharmacistAgent processing started")
        
        # Build conversation history
        messages = state.get("messages", [])
        conversation_history = "No prior messages in this conversation."
        if messages:
            history_parts = []
            for msg in messages[-10:]:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                history_parts.append(f"{role}: {content}")
            if history_parts:
                conversation_history = "\n".join(history_parts)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", PHARMACIST_SYSTEM),
            ("human", "{query}")
        ])
        
        llm_with_tools = self.llm.bind_tools(self.tools)
        chain = prompt | llm_with_tools
        
        try:
            logger.debug("PharmacistAgent invoking LLM chain")
            response = await chain.ainvoke({
                "dosha_profile": state.get("dosha_profile", {}),
                "health_conditions": state.get("health_conditions", []),
                "conversation_history": conversation_history,
                "query": state["user_query"]
            })
            
            # Process tool calls
            safety_results = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "check_contraindication":
                        logger.debug("PharmacistAgent tool call: check_contraindication args=%s", tool_call["args"])
                        result = check_contraindication.invoke(tool_call["args"])
                        logger.debug("PharmacistAgent tool result: check_contraindication")
                        safety_results.append(result)
            
            output = response.content or ""
            if safety_results:
                output = "**Safety Checks:**\n" + "\n".join(safety_results) + "\n\n" + output
            
            # Always add safety note for herb queries
            output += (
                "\n\n💊 **Important Reminder:** These are general guidelines. "
                "Consult a qualified Ayurvedic practitioner before starting any herbal regimen, "
                "especially if you have existing health conditions or take medications."
            )
            
            logger.info("PharmacistAgent processing completed")
            return {
                "worker_output": output,
                "needs_followup": False
            }
            
        except Exception as e:
            logger.exception("PharmacistAgent processing failed")
            return {
                "worker_output": (
                    "I couldn't complete the safety check. For your safety, "
                    "please consult a qualified Ayurvedic practitioner before using any herbs. "
                    f"Technical issue: {str(e)}"
                ),
                "needs_followup": False
            }


# === Worker Agent: Diagnostics (Symptom Analysis) ===

DIAGNOSTICS_SYSTEM = """You are an Ayurvedic Diagnostician specializing in symptom pattern recognition.

Your role is to:
1. Map symptoms to potential Dosha imbalances (NOT disease diagnosis)
2. Identify aggravating factors (diet, lifestyle, season, emotions)
3. Suggest which body systems (Dhatus, Srotas) may be affected
4. Recommend appropriate specialists or follow-up questions

USER PROFILE:
- Prakriti (Constitution): {dosha_profile}
- Known Conditions: {health_conditions}

CONVERSATION HISTORY:
{conversation_history}

CONTEXT FROM HISTORY:
{context_from_graph}

IMPORTANT BOUNDARIES:
- You identify PATTERNS, not diagnose diseases
- Always recommend professional consultation for persistent symptoms
- Frame findings as "This pattern suggests..." not "You have..."
- Prioritize ruling out serious conditions that need medical attention
- Reference earlier parts of the conversation when relevant

SYMPTOM ANALYSIS FRAMEWORK:
1. Which Dosha(s) appear elevated based on these symptoms?
2. Is this acute (recent) or chronic (long-standing)?
3. What time of day/season do symptoms worsen? (Dosha clues)
4. What are the likely aggravating factors?
5. What simple modifications might provide relief?
"""


class DiagnosticsAgent:
    """
    Specialist worker for symptom pattern recognition.
    
    Maps symptoms to Dosha imbalances without making disease diagnoses.
    """
    
    def __init__(self):
        logger.debug("Initializing DiagnosticsAgent")
        self.llm = get_specialist_llm()
    
    async def process(self, state: WorkerState) -> dict:
        """
        Analyze symptoms and map to Dosha patterns.
        """
        logger.info("DiagnosticsAgent processing started")
        context = state.get("context_from_graph") or "No previous consultation history."
        
        # Build conversation history
        messages = state.get("messages", [])
        conversation_history = "No prior messages in this conversation."
        if messages:
            history_parts = []
            for msg in messages[-10:]:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                history_parts.append(f"{role}: {content}")
            if history_parts:
                conversation_history = "\n".join(history_parts)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", DIAGNOSTICS_SYSTEM),
            ("human", "{query}")
        ])
        
        chain = prompt | self.llm
        
        try:
            logger.debug("DiagnosticsAgent invoking LLM chain")
            response = await chain.ainvoke({
                "dosha_profile": state.get("dosha_profile", {}),
                "health_conditions": state.get("health_conditions", []),
                "context_from_graph": context,
                "conversation_history": conversation_history,
                "query": state["user_query"]
            })
            
            output = response.content
            
            # Add mandatory disclaimer for symptom-related queries
            output += (
                "\n\n⚕️ **Note:** This analysis is based on Ayurvedic principles and is not "
                "a medical diagnosis. If symptoms persist or are severe, please consult a "
                "healthcare professional."
            )
            
            logger.info("DiagnosticsAgent processing completed")
            return {
                "worker_output": output,
                "needs_followup": False
            }
            
        except Exception as e:
            logger.exception("DiagnosticsAgent processing failed")
            return {
                "worker_output": f"I need more information to analyze your symptoms properly. Error: {str(e)}",
                "needs_followup": True
            }


# === Worker Agent: Diet & Lifestyle Coach ===

DIET_COACH_SYSTEM = """You are an Ayurvedic Diet & Lifestyle Coach (Pathya-Apathya specialist).

Your expertise includes:
- Personalized diet recommendations based on Dosha
- Seasonal eating (Ritucharya)
- Daily routine optimization (Dinacharya)
- Fasting and cleansing guidelines
- Meal timing and food combinations

USER PROFILE:
- Dosha (Prakriti): {dosha_profile}
- Health Conditions: {health_conditions}

CONVERSATION HISTORY:
{conversation_history}

DIETARY PRINCIPLES:
1. Recommend foods that pacify elevated Doshas
2. Consider current season in your recommendations
3. Explain the energetics (Rasa, Virya, Vipaka) of foods
4. Provide specific, practical meal suggestions
5. Include lifestyle factors (exercise, sleep) that support digestion
6. Reference earlier parts of the conversation when relevant

AVOID:
- Rigid dietary rules without context
- Extreme fasting without appropriate warnings
- Recommendations that conflict with medical conditions
"""


class DietCoach:
    """
    Specialist worker for diet and lifestyle guidance.
    """
    
    def __init__(self):
        logger.debug("Initializing DietCoach")
        self.llm = get_specialist_llm()
        self.tools = [get_dosha_diet_recommendations]
        logger.debug("DietCoach tools: %s", [t.name for t in self.tools])
    
    async def process(self, state: WorkerState) -> dict:
        """
        Provide personalized diet and lifestyle recommendations.
        """
        logger.info("DietCoach processing started")
        
        # Build conversation history
        messages = state.get("messages", [])
        conversation_history = "No prior messages in this conversation."
        if messages:
            history_parts = []
            for msg in messages[-10:]:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                history_parts.append(f"{role}: {content}")
            if history_parts:
                conversation_history = "\n".join(history_parts)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", DIET_COACH_SYSTEM),
            ("human", "{query}")
        ])
        
        llm_with_tools = self.llm.bind_tools(self.tools)
        chain = prompt | llm_with_tools
        
        try:
            logger.debug("DietCoach invoking LLM chain")
            response = await chain.ainvoke({
                "dosha_profile": state.get("dosha_profile", {}),
                "health_conditions": state.get("health_conditions", []),
                "conversation_history": conversation_history,
                "query": state["user_query"]
            })
            
            # Process tool calls
            diet_info = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "get_dosha_diet_recommendations":
                        logger.debug("DietCoach tool call: get_dosha_diet_recommendations args=%s", tool_call["args"])
                        result = get_dosha_diet_recommendations.invoke(tool_call["args"])
                        logger.debug("DietCoach tool result: get_dosha_diet_recommendations")
                        diet_info.append(result)
            
            output = response.content or ""
            if diet_info:
                output = "\n".join(diet_info) + "\n\n**Personalized Guidance:**\n" + output
            
            logger.info("DietCoach processing completed")
            return {
                "worker_output": output,
                "needs_followup": False
            }
            
        except Exception as e:
            logger.exception("DietCoach processing failed")
            return {
                "worker_output": f"I couldn't generate diet recommendations. Error: {str(e)}",
                "needs_followup": True
            }


# === Worker Factory ===

def get_worker(worker_type: str):
    """
    Factory function to get the appropriate worker agent.
    
    Args:
        worker_type: One of "ayurveda", "pharmacist", "diagnostics", "diet"
        
    Returns:
        The worker agent instance
    """
    workers = {
        "ayurveda": AyurvedaSpecialist,
        "pharmacist": PharmacistAgent,
        "diagnostics": DiagnosticsAgent,
        "diet": DietCoach,
    }
    
    logger.info("Selecting worker type: %s", worker_type)
    worker_class = workers.get(worker_type)
    if worker_class is None:
        logger.error("Unknown worker type requested: %s", worker_type)
        raise ValueError(f"Unknown worker type: {worker_type}")
    
    worker_instance = worker_class()
    logger.info("Worker instance created: %s", worker_class.__name__)
    return worker_instance
