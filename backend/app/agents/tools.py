"""
LangChain Tools for Ayurvedic Treatment Planning

These tools wrap deterministic logic so the LLM agents can call them safely.
"""

from langchain_core.tools import tool
from typing import Optional
from ..services.dosha_calculator import get_dosha_calculator
from ..models.dosha import QuestionAnswer


@tool
def assess_dosha_from_answers(answers_json: str) -> str:
    """
    Calculate Prakriti (constitution) scores from questionnaire answers.
    
    Args:
        answers_json: JSON string of answers in format: 
                  [{{"question_id": "PHY_001", "answer_value": 4}}, ...]
    
    Returns:
        String with Vata, Pitta, Kapha scores and dominant constitution.
    """
    import json
    
    try:
        raw_answers = json.loads(answers_json)
        answers = [QuestionAnswer(**a) for a in raw_answers]
    except (json.JSONDecodeError, ValueError) as e:
        return f"Error parsing answers: {e}"
    
    calculator = get_dosha_calculator()
    scores = calculator.calculate_prakriti(answers)
    
    return (
        f"Dosha Scores:\n"
        f"- Vata: {scores.vata:.1%}\n"
        f"- Pitta: {scores.pitta:.1%}\n"
        f"- Kapha: {scores.kapha:.1%}\n"
        f"Dominant Constitution: {scores.constitution_type}\n"
        f"Primary Dosha: {scores.dominant_dosha.value}"
    )


@tool
def assess_dosha_from_vitals(
    heart_rate: Optional[float] = None,
    hrv: Optional[float] = None,
    skin_temp: Optional[float] = None,
    respiration_rate: Optional[float] = None
) -> str:
    """
    Infer current Dosha state (Vikriti) from physiological vitals.
    
    Args:
        heart_rate: Heart rate in BPM (normal: 60-100)
        hrv: Heart Rate Variability in ms (normal: 20-200)
        skin_temp: Skin temperature in Celsius (normal: 33-37)
        respiration_rate: Breaths per minute (normal: 12-20)
    
    Returns:
        String with inferred Dosha tendencies from vitals.
    """
    calculator = get_dosha_calculator()
    scores = calculator.map_vitals_to_dosha(
        heart_rate=heart_rate,
        hrv=hrv,
        skin_temp=skin_temp,
        respiration_rate=respiration_rate
    )
    
    provided_vitals = []
    if heart_rate: provided_vitals.append(f"HR: {heart_rate} BPM")
    if hrv: provided_vitals.append(f"HRV: {hrv} ms")
    if skin_temp: provided_vitals.append(f"Temp: {skin_temp}°C")
    if respiration_rate: provided_vitals.append(f"RR: {respiration_rate}/min")
    
    return (
        f"Vitals Analysis ({', '.join(provided_vitals) or 'No vitals provided'}):\n"
        f"Inferred Dosha State:\n"
        f"- Vata tendency: {scores.vata:.1%}\n"
        f"- Pitta tendency: {scores.pitta:.1%}\n"
        f"- Kapha tendency: {scores.kapha:.1%}\n"
        f"Current dominant: {scores.dominant_dosha.value}"
    )


@tool
def check_contraindication(herb_name: str, condition: str) -> str:
    """
    Check if an herb has contraindications for a specific condition.
    
    This is a safety-critical deterministic check.
    
    Args:
        herb_name: Name of the herb (e.g., "Ashwagandha", "Brahmi")
        condition: Medical condition to check against (e.g., "hyperthyroidism")
    
    Returns:
        Safety assessment with source citation.
    """
    # Deterministic contraindication database
    # Source: Bhavaprakasha Nighantu, API guidelines
    CONTRAINDICATIONS = {
        "ashwagandha": {
            "hyperthyroidism": {
                "severity": "HIGH",
                "reason": "May increase thyroid hormone levels",
                "source": "Bhavaprakasha Nighantu; Modern pharmacological studies"
            },
            "pregnancy": {
                "severity": "HIGH", 
                "reason": "May cause uterine contractions",
                "source": "API Safety Guidelines"
            },
            "autoimmune": {
                "severity": "MODERATE",
                "reason": "May stimulate immune system",
                "source": "Clinical review literature"
            }
        },
        "brahmi": {
            "hypothyroidism": {
                "severity": "MODERATE",
                "reason": "May decrease T4 levels",
                "source": "Pharmacological studies"
            }
        },
        "triphala": {
            "pregnancy": {
                "severity": "HIGH",
                "reason": "Contains herbs with emmenagogue properties",
                "source": "Charaka Samhita"
            },
            "diarrhea": {
                "severity": "MODERATE",
                "reason": "May aggravate loose stools",
                "source": "Charaka Samhita, Chikitsa Sthana"
            }
        },
        "guggulu": {
            "hyperthyroidism": {
                "severity": "MODERATE",
                "reason": "May increase thyroid activity",
                "source": "Bhavaprakasha; Modern studies"
            },
            "bleeding_disorders": {
                "severity": "HIGH",
                "reason": "Has blood-thinning properties",
                "source": "API Guidelines"
            }
        }
    }
    
    herb_lower = herb_name.lower().strip()
    condition_lower = condition.lower().strip().replace(" ", "_")
    
    herb_data = CONTRAINDICATIONS.get(herb_lower)
    if not herb_data:
        return f"No contraindication data found for '{herb_name}'. Recommend consulting practitioner."
    
    contraindication = herb_data.get(condition_lower)
    if not contraindication:
        return (
            f"✓ No known contraindication for {herb_name} with {condition}.\n"
            f"Note: Always verify with qualified practitioner."
        )
    
    return (
        f"⚠️ CONTRAINDICATION FOUND:\n"
        f"Herb: {herb_name}\n"
        f"Condition: {condition}\n"
        f"Severity: {contraindication['severity']}\n"
        f"Reason: {contraindication['reason']}\n"
        f"Source: {contraindication['source']}\n"
        f"Recommendation: Avoid use or consult Ayurvedic practitioner."
    )


@tool
def get_dosha_diet_recommendations(dominant_dosha: str) -> str:
    """
    Get dietary recommendations for balancing a specific Dosha.
    
    Args:
        dominant_dosha: The Dosha to balance - "Vata", "Pitta", or "Kapha"
    
    Returns:
        Dietary guidelines with foods to favor and avoid.
    """
    DIET_GUIDELINES = {
        "vata": {
            "qualities_to_favor": "Warm, moist, grounding, nourishing",
            "tastes_to_favor": "Sweet, Sour, Salty",
            "foods_to_favor": [
                "Cooked grains (rice, oats, wheat)",
                "Root vegetables (carrots, beets, sweet potato)",
                "Warm soups and stews",
                "Ghee and healthy oils",
                "Sweet fruits (bananas, mangoes, grapes)",
                "Warming spices (ginger, cinnamon, cumin)"
            ],
            "foods_to_avoid": [
                "Raw vegetables and salads",
                "Cold foods and drinks",
                "Dry, crunchy snacks",
                "Beans (except mung)",
                "Caffeine excess"
            ],
            "source": "Charaka Samhita, Sutra Sthana"
        },
        "pitta": {
            "qualities_to_favor": "Cool, dry, mild, grounding",
            "tastes_to_favor": "Sweet, Bitter, Astringent",
            "foods_to_favor": [
                "Cooling vegetables (cucumber, leafy greens)",
                "Sweet fruits (melons, pears, coconut)",
                "Basmati rice, wheat, oats",
                "Milk, ghee, coconut oil",
                "Cooling herbs (cilantro, mint, fennel)"
            ],
            "foods_to_avoid": [
                "Spicy, hot foods",
                "Sour and fermented foods",
                "Red meat",
                "Alcohol and caffeine",
                "Fried foods"
            ],
            "source": "Charaka Samhita, Sutra Sthana"
        },
        "kapha": {
            "qualities_to_favor": "Light, warm, dry, stimulating",
            "tastes_to_favor": "Pungent, Bitter, Astringent",
            "foods_to_favor": [
                "Light grains (barley, millet, buckwheat)",
                "Most vegetables, especially leafy greens",
                "Legumes and beans",
                "Light fruits (apples, pears, berries)",
                "Warming spices (black pepper, ginger, turmeric)"
            ],
            "foods_to_avoid": [
                "Heavy, oily foods",
                "Dairy products (except buttermilk)",
                "Sweet and salty foods",
                "Cold foods and drinks",
                "Excessive meat"
            ],
            "source": "Charaka Samhita, Sutra Sthana"
        }
    }
    
    dosha_key = dominant_dosha.lower().strip()
    guidelines = DIET_GUIDELINES.get(dosha_key)
    
    if not guidelines:
        return f"Unknown Dosha: {dominant_dosha}. Please specify Vata, Pitta, or Kapha."
    
    favor_list = "\n  - ".join(guidelines["foods_to_favor"])
    avoid_list = "\n  - ".join(guidelines["foods_to_avoid"])
    
    return (
        f"🍽️ Diet Recommendations for {dominant_dosha} Balance:\n\n"
        f"Qualities to Favor: {guidelines['qualities_to_favor']}\n"
        f"Tastes to Favor: {guidelines['tastes_to_favor']}\n\n"
        f"Foods to Include:\n  - {favor_list}\n\n"
        f"Foods to Minimize:\n  - {avoid_list}\n\n"
        f"Source: {guidelines['source']}"
    )


# Tool collection for agent use
ayurveda_tools = [
    assess_dosha_from_answers,
    assess_dosha_from_vitals,
    check_contraindication,
    get_dosha_diet_recommendations,
]
