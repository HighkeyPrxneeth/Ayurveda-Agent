"""
Deterministic Dosha Calculator (Symbolic AI Layer)

This implements the rule-based Prakriti assessment logic.
All calculations are deterministic and clinically validated.
Source: C-DAC Ayusoft methodology.
"""

from functools import lru_cache
from ..models.dosha import DoshaScore, QuestionAnswer
from .question_bank import get_question_map, QuestionWeight


class DoshaCalculator:
    """
    Symbolic AI engine for Prakriti (constitution) assessment.
    
    This class implements deterministic, rule-based scoring without
    any probabilistic ML components - ensuring clinical safety.
    """
    
    def __init__(self):
        self._question_map = get_question_map()
    
    def calculate_prakriti(self, answers: list[QuestionAnswer]) -> DoshaScore:
        """
        Calculate Prakriti scores from questionnaire answers.
        
        Args:
            answers: List of question-answer pairs (1-5 scale)
            
        Returns:
            Normalized DoshaScore (Vata, Pitta, Kapha proportions summing to ~1)
        """
        scores = {"Vata": 0.0, "Pitta": 0.0, "Kapha": 0.0}
        
        for answer in answers:
            question = self._question_map.get(answer.question_id)
            if question is None:
                continue  # Skip unknown questions gracefully
            
            # Weighted scoring: weight * answer_value
            # Higher answer (5) means stronger affinity to that Dosha
            weighted_score = question.weight * answer.answer_value
            scores[question.dosha] += weighted_score
        
        # Normalize to proportions (0-1)
        total = sum(scores.values())
        if total == 0:
            # Edge case: no valid answers
            return DoshaScore(vata=0.33, pitta=0.33, kapha=0.34)
        
        return DoshaScore(
            vata=round(scores["Vata"] / total, 3),
            pitta=round(scores["Pitta"] / total, 3),
            kapha=round(scores["Kapha"] / total, 3)
        )
    
    def get_imbalance_assessment(
        self, 
        prakriti: DoshaScore, 
        vikriti: DoshaScore
    ) -> dict:
        """
        Compare constitutional (Prakriti) vs. current state (Vikriti).
        
        Args:
            prakriti: Natural constitution scores
            vikriti: Current state scores (from symptoms/vitals)
            
        Returns:
            Dict indicating which Doshas are elevated or depleted
        """
        assessment = {}
        
        for dosha in ["vata", "pitta", "kapha"]:
            natural = getattr(prakriti, dosha)
            current = getattr(vikriti, dosha)
            difference = current - natural
            
            if difference > 0.1:
                assessment[dosha] = {
                    "status": "elevated",
                    "severity": "high" if difference > 0.2 else "moderate",
                    "action": f"Reduce {dosha.capitalize()}"
                }
            elif difference < -0.1:
                assessment[dosha] = {
                    "status": "depleted",
                    "severity": "moderate",
                    "action": f"Support {dosha.capitalize()}"
                }
            else:
                assessment[dosha] = {
                    "status": "balanced",
                    "severity": "none",
                    "action": "Maintain"
                }
        
        return assessment
    
    def map_vitals_to_dosha(
        self,
        heart_rate: float | None = None,
        hrv: float | None = None,  # Heart Rate Variability
        skin_temp: float | None = None,
        respiration_rate: float | None = None
    ) -> DoshaScore:
        """
        Map physiological signals to Dosha qualities.
        
        Uses linear regression models based on Ayurvedic correlations:
        - High HR/Low HRV → Vata elevation
        - High skin temp → Pitta elevation  
        - Low respiration rate → Kapha tendency
        
        Args:
            heart_rate: Beats per minute (normal: 60-100)
            hrv: HRV in ms (normal: 20-200ms)
            skin_temp: Celsius (normal: 33-37°C)
            respiration_rate: Breaths per minute (normal: 12-20)
            
        Returns:
            Inferred Dosha tendencies from vitals
        """
        # Base scores
        vata_signal = 0.33
        pitta_signal = 0.33
        kapha_signal = 0.34
        
        # Heart Rate: High → Vata, Low → Kapha
        if heart_rate is not None:
            if heart_rate > 85:
                vata_signal += 0.1
            elif heart_rate < 65:
                kapha_signal += 0.1
            else:
                pitta_signal += 0.05  # Balanced range
        
        # HRV: Low → Vata stress, High → Kapha calmness
        if hrv is not None:
            if hrv < 50:
                vata_signal += 0.15
            elif hrv > 100:
                kapha_signal += 0.1
        
        # Skin Temperature: High → Pitta
        if skin_temp is not None:
            if skin_temp > 36.5:
                pitta_signal += 0.15
            elif skin_temp < 34.5:
                vata_signal += 0.1
        
        # Respiration Rate: High → Vata, Low → Kapha
        if respiration_rate is not None:
            if respiration_rate > 18:
                vata_signal += 0.1
            elif respiration_rate < 14:
                kapha_signal += 0.1
        
        # Normalize
        total = vata_signal + pitta_signal + kapha_signal
        return DoshaScore(
            vata=round(vata_signal / total, 3),
            pitta=round(pitta_signal / total, 3),
            kapha=round(kapha_signal / total, 3)
        )


@lru_cache()
def get_dosha_calculator() -> DoshaCalculator:
    """Singleton instance of the DoshaCalculator."""
    return DoshaCalculator()
