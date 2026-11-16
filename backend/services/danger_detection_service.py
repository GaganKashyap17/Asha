"""
Danger detection service — deterministic rule engine for ASHA Voice.
Independent of LLM. Implements WHO/IMNCI clinical rules.
"""
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DANGER SIGN REGISTRY
# ---------------------------------------------------------------------------
DANGER_SIGN_REGISTRY = [
    {
        "id": "DS001",
        "category": "obstetric_hemorrhage",
        "name": "Bleeding during pregnancy",
        "source": "WHO Pregnancy, Childbirth, Postpartum and Newborn Care Guide, 2015, Section C1",
        "trigger_phrases": [
            "bleeding", "blood", "hemorrhage", "haemorrhage", "bleed",
            "ரத்தப்போக்கு", "ரத்தம்", "வெளியேறும் ரத்தம்",
            "spotting", "discharge blood",
        ],
        "negation_phrases": [
            "no bleeding", "no blood", "stopped bleeding", "history of bleeding",
            "not bleeding", "no hemorrhage", "past bleeding", "previously bled",
            "denied bleeding", "no spotting",
        ],
        "historical_phrases": [
            "history of", "past", "previously", "earlier", "before pregnancy",
        ],
        "hypothetical_phrases": [
            "if", "what if", "suppose", "in case", "hypothetically",
        ],
        "context_window": 8,
        "severity": "emergency",
        "referral_message_en": (
            "EMERGENCY: This beneficiary shows signs of bleeding during pregnancy. "
            "Refer immediately to the nearest Primary Health Centre (PHC). "
            "Do not wait. This is a medical emergency."
        ),
        "referral_message_ta": (
            "அவசரநிலை: இந்த பயனர் கர்ப்பகால ரத்தப்போக்கு அறிகுறிகள் காட்டுகிறார். "
            "உடனடியாக அருகிலுள்ள ஆரம்ப சுகாதார நிலையத்திற்கு அனுப்புங்கள். காத்திருக்காதீர்கள்."
        ),
        "disclaimer": (
            "This is a referral-support tool, not a diagnostic system. "
            "Always use clinical judgment."
        ),
    },
    {
        "id": "DS002",
        "category": "neonatal_fever",
        "name": "High fever in newborn",
        "source": "IMNCI Guidelines, Ministry of Health and Family Welfare, India, 2014, Chapter 2",
        "trigger_phrases": [
            "fever", "high temperature", "high fever", "febrile", "burning up",
            "காய்ச்சல்", "வெப்பம்", "temperature high", "very hot", "hot to touch",
        ],
        "negation_phrases": [
            "no fever", "fever gone", "afebrile", "no temperature",
            "not feverish", "temperature normal", "fever resolved",
        ],
        "historical_phrases": [
            "history of fever", "had fever before", "past fever",
        ],
        "hypothetical_phrases": [
            "if fever", "what if fever",
        ],
        "context_requirement": "newborn",
        "newborn_context_phrases": [
            "newborn", "baby", "infant", "குழந்தை", "பச்சிளம் குழந்தை",
            "neonatal", "neonate",
        ],
        "context_window": 15,
        "severity": "emergency",
        "referral_message_en": (
            "EMERGENCY: A newborn with high fever requires immediate medical attention. "
            "Refer immediately to the nearest Primary Health Centre (PHC). "
            "This is a medical emergency."
        ),
        "referral_message_ta": (
            "அவசரநிலை: காய்ச்சலுடன் கூடிய புதுவதாகப் பிறந்த குழந்தைக்கு "
            "உடனடி மருத்துவ கவனிப்பு தேவை. "
            "உடனடியாக அருகிலுள்ள ஆரம்ப சுகாதார நிலையத்திற்கு அனுப்புங்கள்."
        ),
        "disclaimer": (
            "This is a referral-support tool, not a diagnostic system. "
            "Always use clinical judgment."
        ),
    },
    {
        "id": "DS003",
        "category": "severe_headache_vision",
        "name": "Severe headache or blurred vision (possible pre-eclampsia)",
        "source": "WHO Pregnancy, Childbirth, Postpartum and Newborn Care Guide, 2015, Section B6",
        "trigger_phrases": [
            "severe headache", "blurred vision", "vision problem", "blurry vision",
            "eclampsia", "pre-eclampsia", "fits", "convulsion", "seizure",
            "தலைவலி", "மங்கலான பார்வை",
        ],
        "negation_phrases": [
            "no headache", "no fits", "no convulsion", "no seizure",
            "not having headache",
        ],
        "historical_phrases": ["history of fits", "past convulsion"],
        "hypothetical_phrases": ["if fits", "what if seizure"],
        "context_window": 10,
        "severity": "emergency",
        "referral_message_en": (
            "EMERGENCY: Severe headache or blurred vision during pregnancy may indicate "
            "pre-eclampsia. Refer immediately to PHC. Do not wait."
        ),
        "referral_message_ta": (
            "அவசரநிலை: கர்ப்ப காலத்தில் கடுமையான தலைவலி அல்லது மங்கலான பார்வை "
            "முன்-இரத்த அழுத்தத்தின் அறிகுறியாக இருக்கலாம். "
            "உடனடியாக PHC-க்கு அனுப்புங்கள்."
        ),
        "disclaimer": (
            "This is a referral-support tool, not a diagnostic system. "
            "Always use clinical judgment."
        ),
    },
    {
        "id": "DS004",
        "category": "neonatal_not_feeding",
        "name": "Newborn not feeding",
        "source": "IMNCI Guidelines, Ministry of Health and Family Welfare, India, 2014, Chapter 2",
        "trigger_phrases": [
            "not feeding", "not breastfeeding", "refusing feed", "poor feeding",
            "unable to feed", "not sucking", "பால் குடிக்கவில்லை",
        ],
        "negation_phrases": [
            "feeding well", "breastfeeding well", "normal feeding",
        ],
        "historical_phrases": ["used to not feed", "previously not feeding"],
        "hypothetical_phrases": ["if not feeding"],
        "context_requirement": "newborn",
        "newborn_context_phrases": [
            "newborn", "baby", "infant", "குழந்தை", "பச்சிளம் குழந்தை",
            "neonatal", "neonate",
        ],
        "context_window": 10,
        "severity": "urgent",
        "referral_message_en": (
            "URGENT: A newborn who is not feeding needs prompt medical evaluation. "
            "Refer to nearest PHC today."
        ),
        "referral_message_ta": (
            "அவசர: பால் குடிக்காத புதுவதாகப் பிறந்த குழந்தைக்கு "
            "உடனடி மருத்துவ மதிப்பீடு தேவை. இன்றே PHC-க்கு அனுப்புங்கள்."
        ),
        "disclaimer": (
            "This is a referral-support tool, not a diagnostic system. "
            "Always use clinical judgment."
        ),
    },
]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------
@dataclass
class DangerSignResult:
    rule_id: str
    category: str
    name: str
    severity: str
    detected: bool
    is_negated: bool
    is_historical: bool
    is_hypothetical: bool
    is_ambiguous: bool
    matched_phrase: str
    context_snippet: str
    referral_message_en: str
    referral_message_ta: str
    source: str
    disclaimer: str


# ---------------------------------------------------------------------------
# Detection function
# ---------------------------------------------------------------------------
def detect_danger_signs(transcript: str, visit_type: str = "") -> List[DangerSignResult]:
    """
    Deterministic danger sign detection. Independent of LLM.
    Returns list of DangerSignResult for all matched rules.
    """
    results: List[DangerSignResult] = []
    text_lower = transcript.lower()

    for rule in DANGER_SIGN_REGISTRY:
        matched_phrase = None

        for phrase in rule["trigger_phrases"]:
            phrase_lower = phrase.lower()
            if phrase_lower in text_lower:
                matched_phrase = phrase
                break

        if matched_phrase is None:
            continue

        # Extract context snippet
        pos = text_lower.find(matched_phrase.lower())
        start_char = max(0, pos - 50)
        end_char = min(len(text_lower), pos + len(matched_phrase) + 50)
        context_snippet = transcript[start_char:end_char]

        # Check negation (full text)
        is_negated = False
        for neg in rule.get("negation_phrases", []):
            if neg.lower() in text_lower:
                is_negated = True
                break

        # Check historical
        is_historical = False
        for hist in rule.get("historical_phrases", []):
            if hist.lower() in text_lower:
                is_historical = True
                break

        # Check hypothetical
        is_hypothetical = False
        for hyp in rule.get("hypothetical_phrases", []):
            if hyp.lower() in text_lower:
                is_hypothetical = True
                break

        # Check context requirement (e.g. newborn context for DS002/DS004)
        has_required_context = True
        if rule.get("context_requirement") == "newborn":
            has_required_context = False
            for np in rule.get("newborn_context_phrases", []):
                if np.lower() in text_lower:
                    has_required_context = True
                    break
            if visit_type in ("newborn", "neonatal"):
                has_required_context = True

        # Final determination
        is_detected = (
            not is_negated
            and not is_historical
            and not is_hypothetical
            and has_required_context
        )
        is_ambiguous = (is_negated or is_historical or not has_required_context) and not is_detected

        results.append(DangerSignResult(
            rule_id=rule["id"],
            category=rule["category"],
            name=rule["name"],
            severity=rule["severity"],
            detected=is_detected,
            is_negated=is_negated,
            is_historical=is_historical,
            is_hypothetical=is_hypothetical,
            is_ambiguous=is_ambiguous,
            matched_phrase=matched_phrase,
            context_snippet=context_snippet,
            referral_message_en=rule["referral_message_en"],
            referral_message_ta=rule["referral_message_ta"],
            source=rule["source"],
            disclaimer=rule["disclaimer"],
        ))

    return results


def summarize_danger_results(results: List[DangerSignResult]) -> dict:
    """Summarize detection results for API response."""
    confirmed = [r for r in results if r.detected]
    return {
        "danger_flag": len(confirmed) > 0,
        "confirmed_dangers": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "severity": r.severity,
                "referral_message_en": r.referral_message_en,
                "referral_message_ta": r.referral_message_ta,
                "source": r.source,
                "disclaimer": r.disclaimer,
            }
            for r in confirmed
        ],
        "all_matches": len(results),
        "ambiguous_matches": sum(1 for r in results if r.is_ambiguous),
    }
