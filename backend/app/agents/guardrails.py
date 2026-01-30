"""
Iron Dome Guardrails - Deterministic Safety Layer

Replaces the LLM "Reviewer" with programmable constraints.
These are hard-coded rules that cannot be bypassed by prompt injection.

Inspired by NVIDIA NeMo Guardrails and Microsoft Guidance.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class GuardrailAction(str, Enum):
    """Action to take when a guardrail is triggered."""
    BLOCK = "block"           # Block the output entirely
    WARN = "warn"             # Add warning but allow output
    REDACT = "redact"         # Remove the problematic content
    ESCALATE = "escalate"     # Flag for human review


@dataclass
class GuardrailViolation:
    """Record of a guardrail violation."""
    rule_name: str
    severity: str  # "critical", "high", "medium", "low"
    action: GuardrailAction
    matched_text: Optional[str] = None
    reason: str = ""


@dataclass
class GuardrailResult:
    """Result of guardrail evaluation."""
    passed: bool
    violations: list[GuardrailViolation] = field(default_factory=list)
    sanitized_output: Optional[str] = None
    fallback_message: Optional[str] = None


class IronDomeGuardrails:
    """
    Deterministic safety layer for Ayurvedic wellness outputs.
    
    Rules are checked in priority order:
    1. Critical medical claims (BLOCK)
    2. Prescription language (BLOCK/WARN)
    3. Dangerous substance mentions (BLOCK)
    4. Absolutist claims (REDACT)
    5. Missing disclaimers (WARN)
    """
    
    # Critical: Claims that could cause serious harm
    CRITICAL_CLAIMS = [
        (r'\b(cure|cures|curing)\s+(cancer|diabetes|hiv|aids|covid|tumor)\b', 
         "Claims to cure serious diseases"),
        (r'\b(stop|quit|discontinue)\s+(taking|your)\s+(insulin|blood\s*thinner|heart\s*medication|chemotherapy)\b',
         "Advises stopping critical medication"),
        (r'\b(guaranteed|100%|definitely|certainly)\s+(cure|heal|fix|eliminate)\b',
         "Guaranteed cure claims"),
        (r'\b(replace|substitute|instead\s*of)\s+(your\s*)?(doctor|medication|treatment|medicine)\b',
         "Suggests replacing medical care"),
        (r'\b(no\s*need|don\'?t\s*need)\s+(for\s*)?(doctor|medical|hospital|medication)\b',
         "Discourages medical care"),
    ]
    
    # High: Prescription-like language without qualification
    PRESCRIPTION_PATTERNS = [
        (r'\btake\s+\d+\s*(mg|ml|grams?|tablets?|capsules?)\b(?!\s*(as\s*suggested|if\s*advised|under\s*guidance))',
         "Specific dosage without qualification"),
        (r'\bprescribe|prescription|rx\b',
         "Prescription language"),
        (r'\bdiagnos(e|is|ed|ing)\s+(you|this|it)\s+(with|as)\b',
         "Diagnostic claims"),
    ]
    
    # Dangerous: Substances that should never be recommended
    DANGEROUS_SUBSTANCES = [
        (r'\b(arsenic|mercury|lead|antimony|aconite|belladonna)\b(?!\s*(poisoning|toxicity|avoid|dangerous))',
         "Toxic substance mention without warning"),
        (r'\b(drink|consume|ingest)\s+(urine|feces|blood)\b',
         "Dangerous ingestion recommendation"),
        (r'\b(inject|injection|intravenous|iv)\s+(herb|herbal|ayurvedic)\b',
         "Dangerous administration route"),
    ]
    
    # Medium: Absolutist language that should be softened
    ABSOLUTIST_PATTERNS = [
        (r'\bwill\s+(definitely|certainly|always|100%)\b',
         "Absolutist prediction"),
        (r'\bnever\s+(fail|fails|failing)\b',
         "Guaranteed success claim"),
        (r'\bonly\s+(way|solution|cure|treatment)\b',
         "Exclusive treatment claim"),
    ]
    
    # Required elements
    REQUIRED_DISCLAIMER = re.compile(
        r'(consult|practitioner|disclaimer|educational|informational|not\s*medical\s*advice)',
        re.IGNORECASE
    )
    
    def __init__(self, user_role: str = "patient"):
        """
        Initialize guardrails with user context.
        
        Args:
            user_role: Role of the user ("patient", "practitioner", "doctor")
        """
        self.user_role = user_role
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile all regex patterns for performance."""
        self._critical = [(re.compile(p, re.IGNORECASE), r) for p, r in self.CRITICAL_CLAIMS]
        self._prescription = [(re.compile(p, re.IGNORECASE), r) for p, r in self.PRESCRIPTION_PATTERNS]
        self._dangerous = [(re.compile(p, re.IGNORECASE), r) for p, r in self.DANGEROUS_SUBSTANCES]
        self._absolutist = [(re.compile(p, re.IGNORECASE), r) for p, r in self.ABSOLUTIST_PATTERNS]
    
    def evaluate(self, output: str, intent: Optional[str] = None) -> GuardrailResult:
        """
        Evaluate an output against all guardrails.
        
        Args:
            output: The LLM-generated output to check
            intent: Optional intent classification for context
            
        Returns:
            GuardrailResult with pass/fail status and any violations
        """
        violations = []
        sanitized = output
        
        # Check critical patterns (BLOCK)
        for pattern, reason in self._critical:
            match = pattern.search(output)
            if match:
                violations.append(GuardrailViolation(
                    rule_name="critical_medical_claim",
                    severity="critical",
                    action=GuardrailAction.BLOCK,
                    matched_text=match.group(0),
                    reason=reason
                ))
        
        # Check prescription patterns (BLOCK for patients, WARN for practitioners)
        for pattern, reason in self._prescription:
            match = pattern.search(output)
            if match:
                action = GuardrailAction.WARN if self.user_role == "practitioner" else GuardrailAction.BLOCK
                violations.append(GuardrailViolation(
                    rule_name="prescription_language",
                    severity="high",
                    action=action,
                    matched_text=match.group(0),
                    reason=reason
                ))
        
        # Check dangerous substances (BLOCK)
        for pattern, reason in self._dangerous:
            match = pattern.search(output)
            if match:
                violations.append(GuardrailViolation(
                    rule_name="dangerous_substance",
                    severity="critical",
                    action=GuardrailAction.BLOCK,
                    matched_text=match.group(0),
                    reason=reason
                ))
        
        # Check absolutist patterns (REDACT)
        for pattern, reason in self._absolutist:
            match = pattern.search(output)
            if match:
                violations.append(GuardrailViolation(
                    rule_name="absolutist_claim",
                    severity="medium",
                    action=GuardrailAction.REDACT,
                    matched_text=match.group(0),
                    reason=reason
                ))
                # Soften the language
                sanitized = pattern.sub(self._soften_absolutist, sanitized)
        
        # Check for required disclaimer (WARN if missing)
        if len(output) > 200 and not self.REQUIRED_DISCLAIMER.search(output):
            violations.append(GuardrailViolation(
                rule_name="missing_disclaimer",
                severity="low",
                action=GuardrailAction.WARN,
                reason="Response lacks wellness disclaimer"
            ))
        
        # Determine overall result
        has_block = any(v.action == GuardrailAction.BLOCK for v in violations)
        
        if has_block:
            return GuardrailResult(
                passed=False,
                violations=violations,
                fallback_message=self._get_fallback_message(violations)
            )
        
        # Add disclaimer if needed
        if any(v.rule_name == "missing_disclaimer" for v in violations):
            sanitized = self._add_disclaimer(sanitized)
        
        return GuardrailResult(
            passed=True,
            violations=violations,
            sanitized_output=sanitized
        )
    
    def _soften_absolutist(self, match: re.Match) -> str:
        """Replace absolutist language with softer alternatives."""
        text = match.group(0).lower()
        
        replacements = {
            "will definitely": "may help",
            "will certainly": "could potentially",
            "will always": "often",
            "will 100%": "may",
            "never fail": "typically support",
            "only way": "one approach",
            "only solution": "a traditional approach",
            "only cure": "one wellness practice",
            "only treatment": "one supportive practice",
        }
        
        for pattern, replacement in replacements.items():
            if pattern in text:
                return replacement
        
        return "may help"  # Default softening
    
    def _add_disclaimer(self, output: str) -> str:
        """Add a standard disclaimer to the output."""
        disclaimer = (
            "\n\n---\n"
            "*This information is for educational and wellness purposes only. "
            "It is not intended as medical advice, diagnosis, or treatment. "
            "Please consult a qualified Ayurvedic practitioner or healthcare "
            "provider before starting any wellness regimen.*"
        )
        return output + disclaimer
    
    def _get_fallback_message(self, violations: list[GuardrailViolation]) -> str:
        """Generate a safe fallback message when output is blocked."""
        critical_rules = [v.reason for v in violations if v.severity == "critical"]
        
        base_message = (
            "I apologize, but I cannot provide that specific recommendation as it "
            "may not be safe or appropriate.\n\n"
        )
        
        if critical_rules:
            base_message += (
                "**Safety Note:** The information requested could potentially involve:\n"
            )
            for reason in critical_rules[:3]:  # Limit to 3 reasons
                base_message += f"- {reason}\n"
        
        base_message += (
            "\n**What I can help with:**\n"
            "- General Ayurvedic wellness principles\n"
            "- Dosha assessment and understanding\n"
            "- Diet and lifestyle recommendations\n"
            "- Connecting you with qualified practitioners\n\n"
            "Please consult a qualified Ayurvedic practitioner or healthcare "
            "provider for personalized medical guidance."
        )
        
        return base_message


class ContentFilter:
    """
    Additional content filtering for inputs.
    
    Blocks prompt injection attempts and inappropriate requests.
    """
    
    # Prompt injection patterns
    INJECTION_PATTERNS = [
        r'ignore\s+(previous|above|all)\s+(instructions?|prompts?)',
        r'disregard\s+(your|the)\s+(training|rules|guidelines)',
        r'pretend\s+(you\s*are|to\s*be)\s+(a|an)',
        r'act\s+as\s+(if|though)\s+you',
        r'roleplay\s+as',
        r'you\s+are\s+now\s+',
        r'new\s+instruction[s]?:',
        r'system\s*prompt\s*:\s*',
        r'\[\s*system\s*\]',
    ]
    
    # Off-topic patterns
    OFF_TOPIC_PATTERNS = [
        r'\b(stock|crypto|bitcoin|invest|trading)\b',
        r'\b(politics|election|government|politician)\b',
        r'\b(religion|god|prayer|worship)\b(?!.*ayurved)',  # Allow spiritual wellness
        r'\b(hack|exploit|jailbreak|bypass)\b',
    ]
    
    def __init__(self):
        self._injection = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
        self._offtopic = [re.compile(p, re.IGNORECASE) for p in self.OFF_TOPIC_PATTERNS]
    
    def filter_input(self, user_input: str) -> tuple[bool, Optional[str]]:
        """
        Filter user input for safety.
        
        Returns:
            Tuple of (is_safe, rejection_message if unsafe)
        """
        # Check for prompt injection
        for pattern in self._injection:
            if pattern.search(user_input):
                return False, (
                    "I'm designed to help with Ayurvedic wellness questions. "
                    "How can I assist with your health and wellness journey?"
                )
        
        # Check for off-topic
        for pattern in self._offtopic:
            if pattern.search(user_input):
                return False, (
                    "I specialize in Ayurvedic wellness and health topics. "
                    "Is there anything related to wellness, diet, lifestyle, "
                    "or Dosha balance I can help you with?"
                )
        
        return True, None


# Singleton instances
_guardrails: Optional[IronDomeGuardrails] = None
_content_filter: Optional[ContentFilter] = None


def get_guardrails(user_role: str = "patient") -> IronDomeGuardrails:
    """Get or create guardrails instance."""
    global _guardrails
    if _guardrails is None or _guardrails.user_role != user_role:
        _guardrails = IronDomeGuardrails(user_role)
    return _guardrails


def get_content_filter() -> ContentFilter:
    """Get or create content filter instance."""
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentFilter()
    return _content_filter
