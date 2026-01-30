"""
Prakriti Assessment Question Bank (C-DAC Ayusoft Standard Compatible)

Each question is mapped to a specific Dosha with weighted scoring.
Source: Adapted from validated Prakriti questionnaires.
"""

from pydantic import BaseModel
from typing import Literal


class QuestionWeight(BaseModel):
    """Defines how a question maps to Dosha scoring."""
    question_id: str
    question_text: str
    category: str  # Physical, Mental, Behavioral
    dosha: Literal["Vata", "Pitta", "Kapha"]
    weight: float = 1.0  # Multiplier for this question's importance


# Validated Prakriti Assessment Questions
# Scale: 1 = Not at all like me, 5 = Exactly like me
PRAKRITI_QUESTIONS: list[QuestionWeight] = [
    # === PHYSICAL CHARACTERISTICS ===
    # Body Frame
    QuestionWeight(
        question_id="PHY_001",
        question_text="I have a thin, light body frame with prominent joints and bones.",
        category="Physical",
        dosha="Vata",
        weight=1.2
    ),
    QuestionWeight(
        question_id="PHY_002",
        question_text="I have a medium, athletic build with good muscle tone.",
        category="Physical",
        dosha="Pitta",
        weight=1.2
    ),
    QuestionWeight(
        question_id="PHY_003",
        question_text="I have a large, sturdy frame with tendency to gain weight easily.",
        category="Physical",
        dosha="Kapha",
        weight=1.2
    ),
    
    # Skin
    QuestionWeight(
        question_id="PHY_004",
        question_text="My skin is dry, rough, and tends to crack, especially in cold weather.",
        category="Physical",
        dosha="Vata",
        weight=1.0
    ),
    QuestionWeight(
        question_id="PHY_005",
        question_text="My skin is warm, sensitive, and prone to rashes, acne, or sunburn.",
        category="Physical",
        dosha="Pitta",
        weight=1.0
    ),
    QuestionWeight(
        question_id="PHY_006",
        question_text="My skin is thick, oily, smooth, and cool to touch.",
        category="Physical",
        dosha="Kapha",
        weight=1.0
    ),
    
    # Hair
    QuestionWeight(
        question_id="PHY_007",
        question_text="My hair is dry, frizzy, and tends to have split ends.",
        category="Physical",
        dosha="Vata",
        weight=0.8
    ),
    QuestionWeight(
        question_id="PHY_008",
        question_text="My hair is fine, straight, and I experience early graying or hair loss.",
        category="Physical",
        dosha="Pitta",
        weight=0.8
    ),
    QuestionWeight(
        question_id="PHY_009",
        question_text="My hair is thick, lustrous, wavy, and grows quickly.",
        category="Physical",
        dosha="Kapha",
        weight=0.8
    ),
    
    # Appetite & Digestion
    QuestionWeight(
        question_id="PHY_010",
        question_text="My appetite is irregular - sometimes strong, sometimes weak.",
        category="Physical",
        dosha="Vata",
        weight=1.1
    ),
    QuestionWeight(
        question_id="PHY_011",
        question_text="I have a strong appetite and become irritable if I miss meals.",
        category="Physical",
        dosha="Pitta",
        weight=1.1
    ),
    QuestionWeight(
        question_id="PHY_012",
        question_text="I have a steady, moderate appetite and can skip meals easily.",
        category="Physical",
        dosha="Kapha",
        weight=1.1
    ),
    
    # Sleep
    QuestionWeight(
        question_id="PHY_013",
        question_text="I am a light sleeper and often wake up during the night.",
        category="Physical",
        dosha="Vata",
        weight=1.0
    ),
    QuestionWeight(
        question_id="PHY_014",
        question_text="I sleep moderately well but may wake up feeling hot.",
        category="Physical",
        dosha="Pitta",
        weight=1.0
    ),
    QuestionWeight(
        question_id="PHY_015",
        question_text="I am a deep, heavy sleeper and find it hard to wake up.",
        category="Physical",
        dosha="Kapha",
        weight=1.0
    ),
    
    # === MENTAL CHARACTERISTICS ===
    # Learning & Memory
    QuestionWeight(
        question_id="MEN_001",
        question_text="I learn quickly but also forget quickly.",
        category="Mental",
        dosha="Vata",
        weight=1.0
    ),
    QuestionWeight(
        question_id="MEN_002",
        question_text="I have a sharp, focused mind with good analytical skills.",
        category="Mental",
        dosha="Pitta",
        weight=1.0
    ),
    QuestionWeight(
        question_id="MEN_003",
        question_text="I learn slowly but have excellent long-term memory.",
        category="Mental",
        dosha="Kapha",
        weight=1.0
    ),
    
    # Stress Response
    QuestionWeight(
        question_id="MEN_004",
        question_text="Under stress, I become anxious, worried, or fearful.",
        category="Mental",
        dosha="Vata",
        weight=1.2
    ),
    QuestionWeight(
        question_id="MEN_005",
        question_text="Under stress, I become irritable, critical, or aggressive.",
        category="Mental",
        dosha="Pitta",
        weight=1.2
    ),
    QuestionWeight(
        question_id="MEN_006",
        question_text="Under stress, I become withdrawn, resistant to change, or depressed.",
        category="Mental",
        dosha="Kapha",
        weight=1.2
    ),
    
    # === BEHAVIORAL CHARACTERISTICS ===
    # Activity Level
    QuestionWeight(
        question_id="BEH_001",
        question_text="I am always active, restless, and find it hard to sit still.",
        category="Behavioral",
        dosha="Vata",
        weight=0.9
    ),
    QuestionWeight(
        question_id="BEH_002",
        question_text="I am goal-oriented, competitive, and like to lead.",
        category="Behavioral",
        dosha="Pitta",
        weight=0.9
    ),
    QuestionWeight(
        question_id="BEH_003",
        question_text="I am calm, steady, and prefer routine and stability.",
        category="Behavioral",
        dosha="Kapha",
        weight=0.9
    ),
    
    # Speech Pattern
    QuestionWeight(
        question_id="BEH_004",
        question_text="I speak quickly, sometimes jump between topics.",
        category="Behavioral",
        dosha="Vata",
        weight=0.8
    ),
    QuestionWeight(
        question_id="BEH_005",
        question_text="I speak clearly, precisely, and can be sharp or critical.",
        category="Behavioral",
        dosha="Pitta",
        weight=0.8
    ),
    QuestionWeight(
        question_id="BEH_006",
        question_text="I speak slowly, thoughtfully, with a melodious voice.",
        category="Behavioral",
        dosha="Kapha",
        weight=0.8
    ),
    
    # Temperature Preference
    QuestionWeight(
        question_id="BEH_007",
        question_text="I dislike cold weather and prefer warm environments.",
        category="Behavioral",
        dosha="Vata",
        weight=1.0
    ),
    QuestionWeight(
        question_id="BEH_008",
        question_text="I dislike hot weather and prefer cool environments.",
        category="Behavioral",
        dosha="Pitta",
        weight=1.0
    ),
    QuestionWeight(
        question_id="BEH_009",
        question_text="I dislike damp, cold weather but can tolerate most conditions.",
        category="Behavioral",
        dosha="Kapha",
        weight=1.0
    ),
    
    # Decision Making
    QuestionWeight(
        question_id="BEH_010",
        question_text="I tend to overthink and have difficulty making decisions.",
        category="Behavioral",
        dosha="Vata",
        weight=0.9
    ),
    QuestionWeight(
        question_id="BEH_011",
        question_text="I make decisions quickly and confidently.",
        category="Behavioral",
        dosha="Pitta",
        weight=0.9
    ),
    QuestionWeight(
        question_id="BEH_012",
        question_text="I take my time with decisions and rarely change my mind.",
        category="Behavioral",
        dosha="Kapha",
        weight=0.9
    ),
]


def get_question_map() -> dict[str, QuestionWeight]:
    """Returns a dictionary for quick lookup by question_id."""
    return {q.question_id: q for q in PRAKRITI_QUESTIONS}
