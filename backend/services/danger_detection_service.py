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
            "presence of bleeding", "bleeding present", "bleeding is present",
            "ரத்தப்போக்கு", "ரத்தம்", "வெளியேறும் ரத்தம்",
            "spotting", "discharge blood", "blood coming out",
            "ರಕ್ತಸ್ರಾವ", "ರಕ್ತ", "रक्तस्राव", "खून", "ब्लीडिंग",
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
    {
        "id": "DS005",
        "category": "irregular_pills_ifa_calcium",
        "name": "Irregular Pills / IFA & Calcium Non-compliance",
        "source": "WHO Antenatal Care Guidelines 2016; MoHFW Anemia Mukt Bharat",
        "trigger_phrases": [
            "irregular pills", "irregular pill", "irregular tablet", "irregular tablets",
            "irregular medicine", "irregular ifa", "irregular calcium", "missed pills",
            "missed tablets", "missed doses", "not taking pills", "not taking medicine",
            "pills irregular", "tablets irregular", "skipped pills", "stopped pills",
            "not consumed", "irregular", "missed dose", "missed pill",
            "மாத்திரை ஒழுங்காக சாப்பிடவில்லை", "மாத்திரை சாப்பிடவில்லை", "முறையற்ற மாத்திரைகள்",
            "ಮಾತ್ರೆ ನಿಯಮಿತವಾಗಿ ತೆಗೆದುಕೊಂಡಿಲ್ಲ", "ಅನಿಯಮಿತ ಮಾತ್ರೆ",
            "अनियमित गोलियां", "दवाई नहीं ली", "गोलियां नहीं खाई",
        ],
        "negation_phrases": [
            "taking regularly", "consumed regularly", "both consumed regularly",
            "no missed pills", "taking daily", "regularly taking", "not irregular",
            "compliant with pills", "no irregular pills",
        ],
        "historical_phrases": ["used to be irregular", "past irregular"],
        "hypothetical_phrases": ["if irregular", "what if missed"],
        "context_window": 10,
        "severity": "emergency",
        "referral_message_en": (
            "EMERGENCY / HIGH RISK: Irregular pills / missed IFA and Calcium tablet doses reported during pregnancy. "
            "Sharply increases maternal risk of severe nutritional anaemia, hemorrhage, and fetal complications. "
            "Immediate adherence counselling, Hb screening, and PHC clinical evaluation required."
        ),
        "referral_message_ta": (
            "அவசரநிலை / அதிக ஆபத்து: கர்ப்ப காலத்தில் முறையற்ற மாத்திரைகள் / விடுபட்ட IFA & கால்சியம் மருந்துகள் உட்கொள்ளல். "
            "கடுமையான ரத்த சோகை மற்றும் சிக்கல்களைத் தடுக்க உடனடியாக PHC மருத்துவரிடம் வழிகாட்டல் பெறவும்."
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
        import re
        is_negated = False
        for neg in rule.get("negation_phrases", []):
            pattern = r"(?<!\w)" + re.escape(neg.lower()) + r"(?!\w)"
            if re.search(pattern, text_lower):
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


def detect_danger_signs_from_record(record: dict, category: str = "") -> List[DangerSignResult]:
    """
    Deterministic clinical danger sign evaluation based directly on structured fields.
    Guarantees that when high-risk or emergency values are selected or extracted into
    the visit record, the danger flag and emergency referral advice are triggered immediately.
    """
    results: List[DangerSignResult] = []
    if not record or not isinstance(record, dict):
        return results

    b_cat = (category or record.get("revisit_category") or record.get("visit_type") or "").lower()

    # 1. Vaginal Bleeding (Presence of bleeding = Emergency)
    vb = str(record.get("vaginal_bleeding") or "").strip().lower()
    if vb in ("yes", "bleeding", "spotting", "present", "true", "active") or ("bleed" in vb and not any(k in vb for k in ("no", "none", "not"))):
        results.append(DangerSignResult(
            rule_id="DS001",
            category="obstetric_hemorrhage",
            name="Bleeding during pregnancy (Presence of Bleeding)",
            severity="emergency",
            detected=True,
            is_negated=False,
            is_historical=False,
            is_hypothetical=False,
            is_ambiguous=False,
            matched_phrase="Presence of Bleeding (Vaginal Bleeding: Yes)",
            context_snippet=f"vaginal_bleeding: {record.get('vaginal_bleeding')}",
            referral_message_en=(
                "EMERGENCY: Presence of vaginal bleeding during pregnancy reported. "
                "Immediate referral to Primary Health Centre (PHC) / Hospital required. Do not wait."
            ),
            referral_message_ta=(
                "அவசரநிலை: கர்ப்பகால ரத்தப்போக்கு அறிகுறி பதிவாகியுள்ளது. "
                "உடனடியாக அருகிலுள்ள ஆரம்ப சுகாதார நிலையத்திற்கு (PHC) அனுப்பவும்."
            ),
            source="WHO Pregnancy, Childbirth, Postpartum and Newborn Care Guide, 2015, Section C1",
            disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
        ))

    # 2. Irregular Pills / IFA & Calcium Non-compliance = Emergency / High Risk
    ifa = str(record.get("ifa_calcium_consumption") or "").strip().lower()
    if any(k in ifa for k in ("irregular", "miss", "not consumed", "stopped", "none")) and not any(k in ifa for k in ("both consumed regularly", "regularly", "compliant")):
        results.append(DangerSignResult(
            rule_id="DS005",
            category="irregular_pills_ifa_calcium",
            name="Irregular Pills / IFA & Calcium Non-compliance",
            severity="emergency",
            detected=True,
            is_negated=False,
            is_historical=False,
            is_hypothetical=False,
            is_ambiguous=False,
            matched_phrase="Irregular Pills (IFA & Calcium: Irregular / Missed Doses)",
            context_snippet=f"ifa_calcium_consumption: {record.get('ifa_calcium_consumption')}",
            referral_message_en=(
                "EMERGENCY / HIGH RISK: Irregular pills / missed IFA and Calcium tablet doses reported during pregnancy. "
                "Sharply increases maternal risk of severe nutritional anaemia, hemorrhage, and fetal complications. "
                "Immediate adherence counselling, Hb screening, and PHC clinical evaluation required."
            ),
            referral_message_ta=(
                "அவசரநிலை / அதிக ஆபத்து: கர்ப்ப காலத்தில் முறையற்ற மாத்திரைகள் / விடுபட்ட IFA & கால்சியம் மருந்துகள் உட்கொள்ளல். "
                "கடுமையான ரத்த சோகை மற்றும் சிக்கல்களைத் தடுக்க உடனடியாக PHC மருத்துவரிடம் வழிகாட்டல் பெறவும்."
            ),
            source="WHO Antenatal Care Guidelines 2016; MoHFW Anemia Mukt Bharat",
            disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
        ))

    # 3. Severe Headache / Blurred Vision
    sh = str(record.get("severe_headache_blurred_vision") or "").strip().lower()
    if sh in ("yes", "severe", "blurred vision", "headache") and not any(k in sh for k in ("no", "none", "nil")):
        results.append(DangerSignResult(
            rule_id="DS003",
            category="severe_headache_vision",
            name="Severe Headache / Blurred Vision (Pre-eclampsia Risk)",
            severity="emergency",
            detected=True,
            is_negated=False,
            is_historical=False,
            is_hypothetical=False,
            is_ambiguous=False,
            matched_phrase="Severe Headache / Blurred Vision",
            context_snippet=f"severe_headache_blurred_vision: {record.get('severe_headache_blurred_vision')}",
            referral_message_en=(
                "EMERGENCY: Severe headache or blurred vision during pregnancy may indicate pre-eclampsia. "
                "Refer immediately to PHC. Do not wait."
            ),
            referral_message_ta="அவசரநிலை: கர்ப்ப காலத்தில் கடுமையான தலைவலி அல்லது மங்கலான பார்வை. உடனடியாக PHC-க்கு அனுப்பவும்.",
            source="WHO Pregnancy, Childbirth, Postpartum and Newborn Care Guide, 2015, Section B6",
            disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
        ))

    # 4. Fetal Movement
    fm = str(record.get("fetal_movement") or "").strip().lower()
    if fm in ("absent", "reduced", "no movement", "decreased"):
        results.append(DangerSignResult(
            rule_id="DS006",
            category="fetal_distress",
            name="Reduced / Absent Fetal Movement",
            severity="emergency",
            detected=True,
            is_negated=False,
            is_historical=False,
            is_hypothetical=False,
            is_ambiguous=False,
            matched_phrase="Fetal Movement Absent/Reduced",
            context_snippet=f"fetal_movement: {record.get('fetal_movement')}",
            referral_message_en=(
                "EMERGENCY: Reduced or absent fetal movement reported. Urgent fetal evaluation and PHC / hospital referral required immediately."
            ),
            referral_message_ta="அவசரநிலை: குழந்தையின் அசைவு குறைந்துள்ளது அல்லது இல்லை. உடனடியாக மருத்துவரிடம் செல்லவும்.",
            source="WHO Antenatal Care Guidelines",
            disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
        ))

    # 5. Elevated Blood Pressure (systolic >= 140 or diastolic >= 90)
    sys_val = None
    dia_val = None
    try:
        if record.get("blood_pressure_systolic"):
            sys_val = int(record["blood_pressure_systolic"])
        if record.get("blood_pressure_diastolic"):
            dia_val = int(record["blood_pressure_diastolic"])
        if not sys_val and record.get("blood_pressure"):
            import re
            m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", str(record["blood_pressure"]))
            if m:
                sys_val, dia_val = int(m.group(1)), int(m.group(2))
    except Exception:
        pass

    if (sys_val and sys_val >= 140) or (dia_val and dia_val >= 90):
        results.append(DangerSignResult(
            rule_id="DS007",
            category="hypertension_preeclampsia",
            name=f"Severe Hypertension ({sys_val or '?'}/{dia_val or '?'} mmHg)",
            severity="emergency",
            detected=True,
            is_negated=False,
            is_historical=False,
            is_hypothetical=False,
            is_ambiguous=False,
            matched_phrase=f"High Blood Pressure {sys_val}/{dia_val}",
            context_snippet=f"blood_pressure: {sys_val}/{dia_val}",
            referral_message_en=(
                "EMERGENCY: Blood pressure is dangerously elevated (>= 140/90 mmHg). High risk of pre-eclampsia. Immediate PHC referral required."
            ),
            referral_message_ta="அவசரநிலை: இரத்த அழுத்தம் மிக அதிகமாக உள்ளது. உடனடியாக மருத்துவமனைக்கு அனுப்பவும்.",
            source="WHO Guidelines for Pre-eclampsia and Eclampsia",
            disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
        ))

    # 6. Severe Anaemia (Hb < 7.0 g/dL)
    try:
        hb_val = float(record.get("hb_level")) if record.get("hb_level") is not None else None
        if hb_val and hb_val < 7.0:
            results.append(DangerSignResult(
                rule_id="DS008",
                category="severe_anaemia",
                name=f"Severe Anaemia (Hb: {hb_val} g/dL)",
                severity="emergency",
                detected=True,
                is_negated=False,
                is_historical=False,
                is_hypothetical=False,
                is_ambiguous=False,
                matched_phrase=f"Hb {hb_val} g/dL",
                context_snippet=f"hb_level: {hb_val}",
                referral_message_en=(
                    "EMERGENCY: Severe anaemia detected (Hb < 7.0 g/dL). High risk of maternal cardiac failure and hemorrhage. Immediate hospital referral required."
                ),
                referral_message_ta="அவசரநிலை: கடுமையான ரத்த சோகை (Hb < 7 g/dL). உடனடியாக மருத்துவமனைக்கு அனுப்பவும்.",
                source="MoHFW Anemia Mukt Bharat Guidelines",
                disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
            ))
    except Exception:
        pass

    # Newborn-specific checks
    if b_cat in ("newborn", "neonatal"):
        if str(record.get("difficulty_in_feeding") or "").strip().lower() in ("yes", "true", "present"):
            results.append(DangerSignResult(
                rule_id="DS004",
                category="neonatal_not_feeding",
                name="Newborn Not Feeding / Inability to Latch",
                severity="emergency",
                detected=True,
                is_negated=False,
                is_historical=False,
                is_hypothetical=False,
                is_ambiguous=False,
                matched_phrase="difficulty_in_feeding: Yes",
                context_snippet="difficulty_in_feeding: Yes",
                referral_message_en="EMERGENCY: Newborn unable to feed. Urgent evaluation at PHC required today.",
                referral_message_ta="அவசரநிலை: குழந்தை பால் குடிக்கவில்லை. இன்றே PHC-க்கு அனுப்பவும்.",
                source="IMNCI Guidelines, MoHFW",
                disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
            ))
        if str(record.get("yellowing_skin_eyes") or "").strip().lower() in ("yes", "true", "present"):
            results.append(DangerSignResult(
                rule_id="DS009",
                category="neonatal_jaundice",
                name="Neonatal Jaundice (Yellowing Skin / Eyes)",
                severity="emergency",
                detected=True,
                is_negated=False,
                is_historical=False,
                is_hypothetical=False,
                is_ambiguous=False,
                matched_phrase="yellowing_skin_eyes: Yes",
                context_snippet="yellowing_skin_eyes: Yes",
                referral_message_en="EMERGENCY: Noticeable jaundice in newborn. Immediate medical evaluation at PHC needed.",
                referral_message_ta="அவசரநிலை: குழந்தைக்கு மஞ்சள் காமாலை அறிகுறி. உடனடியாக PHC-க்கு அனுப்பவும்.",
                source="IMNCI Guidelines, MoHFW",
                disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
            ))
        cord = str(record.get("umbilical_cord_condition") or "").strip().lower()
        if any(k in cord for k in ("pus", "redness", "discharge", "smell", "foul")):
            results.append(DangerSignResult(
                rule_id="DS010",
                category="neonatal_cord_infection",
                name="Umbilical Cord Infection (Redness / Pus)",
                severity="emergency",
                detected=True,
                is_negated=False,
                is_historical=False,
                is_hypothetical=False,
                is_ambiguous=False,
                matched_phrase="umbilical_cord_condition: Redness/Pus",
                context_snippet=f"umbilical_cord_condition: {record.get('umbilical_cord_condition')}",
                referral_message_en="EMERGENCY: Umbilical cord discharge or infection carries high risk of neonatal sepsis. Immediate PHC referral required.",
                referral_message_ta="அவசரநிலை: தொப்புள் கொடி தொற்று. உடனடியாக PHC-க்கு அனுப்பவும்.",
                source="IMNCI Guidelines, MoHFW",
                disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
            ))
        try:
            temp = float(record.get("temperature_celsius")) if record.get("temperature_celsius") is not None else None
            if temp and temp >= 38.0:
                results.append(DangerSignResult(
                    rule_id="DS002",
                    category="neonatal_fever",
                    name=f"High Fever in Newborn ({temp}°C)",
                    severity="emergency",
                    detected=True,
                    is_negated=False,
                    is_historical=False,
                    is_hypothetical=False,
                    is_ambiguous=False,
                    matched_phrase=f"Temperature {temp}°C",
                    context_snippet=f"temperature_celsius: {temp}",
                    referral_message_en="EMERGENCY: Newborn high fever requires immediate medical attention at nearest PHC.",
                    referral_message_ta="அவசரநிலை: குழந்தைக்கு அதிக காய்ச்சல். உடனடியாக PHC-க்கு அனுப்பவும்.",
                    source="IMNCI Guidelines, MoHFW",
                    disclaimer="This is a referral-support tool, not a diagnostic system. Always use clinical judgment.",
                ))
        except Exception:
            pass

    return results
