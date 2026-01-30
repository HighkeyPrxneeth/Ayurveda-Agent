from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RecommendationType(str, Enum):
    """Categories of Ayurvedic recommendations."""
    DIET = "diet"
    LIFESTYLE = "lifestyle"
    HERB = "herb"
    YOGA = "yoga"
    MEDITATION = "meditation"


class Contraindication(BaseModel):
    """A contraindication or safety warning."""
    condition: str = Field(..., description="Medical condition or state")
    severity: str = Field(..., description="low, medium, high")
    recommendation: str = Field(..., description="What to avoid or consult")
    source: str = Field(..., description="Source text reference for traceability")


class Recommendation(BaseModel):
    """A single treatment recommendation."""
    type: RecommendationType
    title: str = Field(..., description="Short title")
    description: str = Field(..., description="Detailed description")
    dosha_effect: dict[str, str] = Field(
        default_factory=dict,
        description="Effect on each Dosha: 'increases', 'decreases', 'balances'"
    )
    contraindications: list[Contraindication] = Field(default_factory=list)
    source: str = Field(..., description="Source text for traceability (e.g., Charaka Samhita)")


class TreatmentPlan(BaseModel):
    """Complete personalized treatment plan."""
    user_query: str = Field(..., description="Original user query")
    dosha_context: dict[str, float] = Field(..., description="User's current Dosha scores")
    recommendations: list[Recommendation] = Field(default_factory=list)
    reasoning: str = Field(..., description="Agent's reasoning for recommendations")
    safety_notes: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default="This is for educational/wellness purposes only. Not a medical diagnosis. Consult a qualified practitioner.",
        description="Legal disclaimer"
    )
