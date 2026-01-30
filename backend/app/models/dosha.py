from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class DoshaType(str, Enum):
    """The three fundamental bio-energies in Ayurveda."""
    VATA = "Vata"
    PITTA = "Pitta"
    KAPHA = "Kapha"


class QuestionAnswer(BaseModel):
    """A single question-answer pair from the Prakriti questionnaire."""
    question_id: str = Field(..., description="Unique identifier for the question")
    answer_value: int = Field(..., ge=1, le=5, description="Answer on 1-5 scale")


class DoshaScore(BaseModel):
    """Normalized Dosha constitution scores."""
    vata: float = Field(..., ge=0, le=1, description="Vata proportion (0-1)")
    pitta: float = Field(..., ge=0, le=1, description="Pitta proportion (0-1)")
    kapha: float = Field(..., ge=0, le=1, description="Kapha proportion (0-1)")
    
    @property
    def dominant_dosha(self) -> DoshaType:
        """Returns the dominant Dosha type."""
        scores = {"Vata": self.vata, "Pitta": self.pitta, "Kapha": self.kapha}
        return DoshaType(max(scores, key=scores.get))
    
    @property
    def constitution_type(self) -> str:
        """Returns the Prakriti constitution type (e.g., 'Vata-Pitta')."""
        sorted_doshas = sorted(
            [("Vata", self.vata), ("Pitta", self.pitta), ("Kapha", self.kapha)],
            key=lambda x: x[1],
            reverse=True
        )
        # If top two are close (within 0.1), it's a dual constitution
        if sorted_doshas[0][1] - sorted_doshas[1][1] < 0.1:
            return f"{sorted_doshas[0][0]}-{sorted_doshas[1][0]}"
        return sorted_doshas[0][0]


class PrakritiAssessment(BaseModel):
    """Complete Prakriti assessment request."""
    answers: list[QuestionAnswer] = Field(..., min_length=1)
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    include_recommendations: bool = Field(False, description="Include basic recommendations")
