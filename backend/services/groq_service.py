"""
Groq LLM service for ASHA Voice — chat completion and data extraction.
"""
import os
import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GroqService:
    """Wraps Groq API for chat and structured extraction."""

    def __init__(self):
        self._api_key = os.environ.get('GROQ_API_KEY', '')
        self._model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
        self._client = None

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self):
        if not self._api_key or self._api_key == 'your_groq_api_key_here':
            raise ValueError("GROQ_API_KEY not configured")
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        return self._client

    def _redact(self, msg: str) -> str:
        if self._api_key and self._api_key in msg:
            return msg.replace(self._api_key, "[REDACTED]")
        return msg

    def validate_connection(self) -> dict:
        """Validate Groq API connection. Never logs the API key."""
        try:
            start = time.time()
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "Reply with just: OK"}],
                max_tokens=5,
            )
            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "success": True,
                "model": self._model,
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as e:
            error_type = type(e).__name__
            error_msg = self._redact(str(e))
            return {
                "success": False,
                "model": self._model,
                "latency_ms": None,
                "error": f"{error_type}: {error_msg}",
            }

    def extract_visit_data(self, transcript: str, visit_type: str) -> dict:
        """Extract structured healthcare data from Tamil+English transcript."""
        system_prompt = """You are a healthcare data extraction assistant for ASHA workers in India.

Your task: Extract structured visit data from Tamil+English mixed speech transcripts.

RULES:
- Extract ONLY information explicitly stated in the transcript
- NEVER invent beneficiary names, dates, or measurements
- Use null for any field not mentioned
- Distinguish "not mentioned" from "false"
- Preserve decimal values exactly as spoken (2.8 not 3)
- For dates: infer year as current year if only month/day spoken
- Weight in transcript may be in kg — extract as float
- ANC = Antenatal checkup
- IFA = Iron and Folic Acid tablet

Return ONLY valid JSON matching this exact schema:
{
  "beneficiary_name": string or null,
  "beneficiary_id": string or null,
  "visit_type": "pregnancy"|"newborn"|"postnatal"|"immunisation"|"household",
  "visit_date": "YYYY-MM-DD" or null,
  "pregnancy_month": integer or null,
  "weight_kg": float or null,
  "anc_completed": true|false|null,
  "ifa_given": true|false|null,
  "vaccinations": [],
  "danger_signs": [],
  "danger_flag": false,
  "next_visit_date": "YYYY-MM-DD" or null,
  "pending_actions": [],
  "missing_fields": [],
  "uncertain_fields": [],
  "confirmation_status": "pending",
  "confidence_score": float 0.0-1.0
}"""

        user_prompt = f"""Visit type: {visit_type}
Transcript: {transcript}

Extract the visit data. Today's date is 2026-11-16."""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            return json.loads(raw)
        except Exception as e:
            error_msg = self._redact(str(e))
            logger.error(f"Groq extraction failed: {type(e).__name__}")
            raise

    def chat(self, messages: list, max_tokens: int = 500) -> str:
        """Generic chat completion."""
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq chat failed: {type(e).__name__}")
            raise

    def extract_beneficiary_registration(self, transcript: str, beneficiary_type: str) -> dict:
        """Extract structured new beneficiary data from voice transcript based on selected category."""
        today = __import__('datetime').date.today().isoformat()
        
        if beneficiary_type == 'pregnant_woman':
            schema = '''{
  "name": string or null,
  "age": integer or null,
  "address": string or null,
  "household": string or null,
  "village": string or null,
  "phone": string or null,
  "pregnancy_registration_status": "registered"|"completed"|"pending"|string or null,
  "lmp": "YYYY-MM-DD" or null,
  "edd": "YYYY-MM-DD" or null,
  "gestational_age_weeks": integer or null,
  "gravida": integer or null,
  "previous_live_births": integer or null,
  "previous_complications": "None reported"|"string description of complication"|"Unknown" or null,
  "gender": "female"
}'''
            type_hint = "Pregnant Woman"
            extra_instructions = """
- LMP = Last Menstrual Period (date YYYY-MM-DD)
- EDD = Expected Date of Delivery (date YYYY-MM-DD)
- Gestational age in weeks as an integer
- Gravida = total number of previous pregnancies
- Previous live births as integer
- For previous complications: if user states "no complications" or "no problems", extract "None reported"; if complications mentioned, extract the details; if not mentioned at all, use null.
"""

        elif beneficiary_type == 'newborn':
            schema = '''{
  "name": string or null,
  "baby_name": string or null,
  "dob": "YYYY-MM-DD" or null,
  "gender": "male"|"female"|"other" or null,
  "mother_name": string or null,
  "mother_beneficiary_id": "PREG-xxxxxx"|"BENxxx" or null,
  "place_of_delivery": string or null,
  "birth_weight_kg": float or null,
  "address": string or null,
  "village": string or null,
  "household": string or null
}'''
            type_hint = "Newborn Baby"
            extra_instructions = """
- Mother's Beneficiary ID if spoken (e.g. PREG-000001, BEN001)
- Mother's name if spoken
- Place of delivery: e.g. "Government Hospital, Coimbatore", "PHC", "Home"
- Birth weight in kg as float (e.g. 2.8)
"""

        elif beneficiary_type == 'immunization_child':
            schema = '''{
  "name": string or null,
  "child_name": string or null,
  "dob": "YYYY-MM-DD" or null,
  "gender": "male"|"female"|"other" or null,
  "mother_name": string or null,
  "mother_beneficiary_id": "PREG-xxxxxx"|"BENxxx" or null,
  "immunization_card_status": "yes"|"no"|"unknown" or null,
  "vaccination_status": string describing received, pending, or missed doses, or null,
  "vaccinations_received": [] list of vaccine names received,
  "vaccinations_pending": [] list of vaccine names pending,
  "address": string or null,
  "village": string or null
}'''
            type_hint = "Immunization / Child"
            extra_instructions = """
- Immunization card availability: "yes" if available, "no" if not available, "unknown"
- Vaccination status: capture whether vaccines are received, pending, or missed
- Extract names of specific vaccines only if explicitly mentioned
"""

        else:  # other
            schema = '''{
  "name": string or null,
  "phone": string (10 digits) or null,
  "beneficiary_category": string or null,
  "address": string or null,
  "village": string or null,
  "household": string or null,
  "emergency_contact": string or null,
  "blood_group": "A+"| "A-"|"B+"| "B-"|"AB+"| "AB-"|"O+"| "O-"|"Unknown" or null
}'''
            type_hint = "Other Beneficiary (Elderly / Adolescent / General Adult)"
            extra_instructions = """
- Beneficiary category: e.g. "Elderly Care", "Adolescent Health", "General Adult"
- Phone: 10 digit Indian mobile number
- Emergency contact: phone or contact name/number
- Blood group: A+, A-, B+, B-, AB+, AB-, O+, O-, or Unknown
"""

        system_prompt = f"""You are a healthcare data extraction assistant for ASHA workers in India.
Extract structured beneficiary registration data from Tamil+English mixed speech transcripts.

RULES:
- Extract ONLY information explicitly stated in the transcript
- NEVER invent names, dates, phone numbers, or medical information
- Use null for any field not mentioned
- Beneficiary Category: {type_hint}
{extra_instructions}

Return ONLY valid JSON matching this exact schema:
{schema}"""

        user_prompt = f"Beneficiary Category: {type_hint}\\nTranscript: {transcript}\\n\\nToday's date is {today}. Extract the registration data."

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2048,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Beneficiary extraction failed: {type(e).__name__}")
            raise


    def _parse_identity_regex(self, transcript: str) -> dict:
        """Deterministic regex parsing for Beneficiary ID and Name from spoken speech."""
        import re
        t = transcript.strip()
        b_id = None
        name = None

        # Convert spoken digits in English, Kannada, Hindi, Tamil
        word_digits = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
            "ಒಂದು": "1", "ಎರಡು": "2", "ಮೂರು": "3", "ನಾಲ್ಕು": "4", "ಐದು": "5",
            "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5",
            "ஒன்று": "1", "இரண்டு": "2", "மூன்று": "3", "நான்கு": "4", "ஐந்து": "5",
        }
        norm_t = t
        for w, d in word_digits.items():
            norm_t = re.sub(rf"\b{re.escape(w)}\b", d, norm_t, flags=re.I)

        # Match ID pattern: PREG, NEWB, IMM, BEN (e.g. PREG-2026-000001, PREG-000001, PREG 001, PREG 1, BEN001)
        m = re.search(r"\b(PREG|NEWB|IMM|BEN)[-_ ]?((?:202[4-9]|203[0-9])[-_ ]?)?(\d+)\b", norm_t, re.I)
        if m:
            pfx = m.group(1).upper()
            yr = re.sub(r"\D", "", m.group(2) or "")
            num = m.group(3)
            if yr:
                b_id = f"{pfx}-{yr}-{num.zfill(6)}"
            elif len(num) >= 4:
                b_id = f"{pfx}-{num.zfill(6)}"
            else:
                b_id = f"{pfx}{num.zfill(3)}"
            clean_text = norm_t[:m.start()] + " " + norm_t[m.end():]
        else:
            clean_text = norm_t

        # Strip common prefixes to extract spoken name
        clean_text = re.sub(r"\b(beneficiary|patient|mother|baby|child|name|is|her|his|id|number|for|revisit|the|visit)\b", " ", clean_text, flags=re.I)
        clean_text = re.sub(r"[^\w\s]", " ", clean_text).strip()
        words = [w for w in clean_text.split() if len(w) >= 2 and w.isalpha() and not w.isdigit()]
        if words:
            name = " ".join(words).title()

        return {"beneficiary_id": b_id, "spoken_name": name}

    def extract_revisit_identity(self, transcript: str) -> dict:
        """Extract beneficiary ID and name from revisit speech."""
        direct = self._parse_identity_regex(transcript)

        system_prompt = """You are a healthcare data extraction assistant for ASHA workers in India.
Extract the beneficiary ID and name from a revisit speech transcript.

RULES:
- Beneficiary IDs may follow:
  * Category IDs: PREG-YYYY-XXXXXX, PREG-XXXXXX, PREG xxx, PREG x (e.g. "PREG-2026-000001", "PREG 001", "PREG 1")
  * NEWB-YYYY-XXXXXX, NEWB-XXXXXX, NEWB xxx, NEWB x (e.g. "NEWB-2026-000001", "NEWB 001")
  * IMM-YYYY-XXXXXX, IMM-XXXXXX, IMM xxx, IMM x (e.g. "IMM-2026-000001", "IMM 001")
  * Legacy IDs: BEN followed by digits (e.g. BEN001, BEN 001, BEN 1)
- Spoken forms may include: "PREG zero zero one", "PREG one", "beneficiary Lakshmi PREG 001", "BEN zero zero one" -> normalize properly
- Extract the spoken name (e.g. "Lakshmi", "Anushka", "Meena", etc.)
- Use null if not mentioned

Return ONLY valid JSON:
{
  "beneficiary_id": string or null,
  "spoken_name": string or null
}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Transcript: {transcript}"},
                ],
                max_tokens=1024,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                parsed = json.loads(content)
                b_id = parsed.get("beneficiary_id") or direct.get("beneficiary_id")
                name = parsed.get("spoken_name") or direct.get("spoken_name")
                return {"beneficiary_id": b_id, "spoken_name": name}
        except Exception as e:
            logger.warning(f"Revisit identity LLM call failed ({type(e).__name__}); using regex extraction")

        return direct

    def extract_revisit_clinical(self, transcript: str, beneficiary_type: str) -> dict:
        """Extract clinical visit data for a revisit across all categories."""
        today = __import__('datetime').date.today().isoformat()
        b_type = (beneficiary_type or "pregnant_woman").lower()
        
        if b_type in ('pregnant_woman', 'pregnancy'):
            schema = '''{
  "visit_type": "pregnancy",
  "visit_date": "YYYY-MM-DD" or null,
  "weight_kg": float or null,
  "blood_pressure": "systolic/diastolic e.g. 120/80" or null,
  "blood_pressure_systolic": integer or null,
  "blood_pressure_diastolic": integer or null,
  "hb_level": float or null,
  "blood_sugar_level": float or null,
  "vaginal_bleeding": "None" | "string description" or null,
  "severe_headache_blurred_vision": "No" | "string description" or null,
  "fetal_movement": "Normal" | "Decreased" | "Active" or null,
  "ifa_calcium_consumption": "Regular" | "Irregular" | "Not taking" or null,
  "pregnancy_month": integer or null,
  "ifa_given": true|false|null,
  "calcium_given": true|false|null,
  "symptoms": [] list of strings,
  "danger_signs": [] list of strings,
  "next_visit_date": "YYYY-MM-DD" or null
}'''
            category_instructions = """
CATEGORY 1: PREGNANT WOMAN REVISIT MANDATORY OBSERVATIONS:
1. Current Weight (kg) -> weight_kg (float e.g. 55.5)
2. Blood Pressure (mmHg) -> blood_pressure ("120/80"), blood_pressure_systolic (int), blood_pressure_diastolic (int)
3. Haemoglobin Level (g/dL) -> hb_level (float e.g. 11.2)
4. Blood Sugar Level (mg/dL) -> blood_sugar_level (float e.g. 110.0)
5. Vaginal Bleeding -> vaginal_bleeding ("None" if no bleeding reported, else description)
6. Severe Headache or Blurred Vision -> severe_headache_blurred_vision ("No" if none, else description)
7. Fetal Movement -> fetal_movement ("Normal" / "Active" / "Decreased")
8. IFA and Calcium Tablet Consumption -> ifa_calcium_consumption ("Regular" if taking tablets daily, else status)
"""
        elif b_type in ('newborn',):
            schema = '''{
  "visit_type": "newborn",
  "visit_date": "YYYY-MM-DD" or null,
  "weight_kg": float or null,
  "temperature_celsius": float or null,
  "respiratory_rate": integer or null,
  "breastfeeding_status": "Exclusive" | "Partial" | "Formula" or null,
  "difficulty_in_feeding": "No" | "None" | "string description" or null,
  "difficulty_in_breathing": "No" | "None" | "string description" or null,
  "yellowing_skin_eyes": "No" | "None" | "Mild jaundice" or null,
  "umbilical_cord_condition": "Clean and dry" | "Normal" | "Infected" or null,
  "symptoms": [] list of strings,
  "danger_signs": [] list of strings,
  "next_visit_date": "YYYY-MM-DD" or null
}'''
            category_instructions = """
CATEGORY 2: NEWBORN REVISIT MANDATORY OBSERVATIONS:
1. Current Weight (kg) -> weight_kg (float e.g. 3.2)
2. Body Temperature (°C) -> temperature_celsius (float e.g. 36.8)
3. Respiratory Rate (breaths/min) -> respiratory_rate (int e.g. 42)
4. Breastfeeding Status -> breastfeeding_status ("Exclusive" if only breast milk, else description)
5. Difficulty in Feeding -> difficulty_in_feeding ("No" / "None" if feeding normally, else description)
6. Difficulty in Breathing -> difficulty_in_breathing ("No" / "None" if breathing normally, else description)
7. Yellowing of Skin or Eyes -> yellowing_skin_eyes ("No" / "None" if clear, else description)
8. Umbilical Cord Condition -> umbilical_cord_condition ("Clean and dry" / "Normal" if healthy, else description)
"""
        else:  # immunization_child / immunisation
            schema = '''{
  "visit_type": "immunisation",
  "visit_date": "YYYY-MM-DD" or null,
  "weight_kg": float or null,
  "height_cm": float or null,
  "general_health_condition": "Good" | "Normal" | "string description" or null,
  "vaccines_due_today": "names of vaccines due e.g. OPV-1, Pentavalent-1" or null,
  "vaccines_given_today": "names of vaccines given e.g. OPV-1, Pentavalent-1" or null,
  "missed_vaccination_doses": "None" | "names of missed vaccines" or null,
  "previous_aefi": "None reported" | "string description" or null,
  "next_vaccination_due_date": "YYYY-MM-DD" or null,
  "next_visit_date": "YYYY-MM-DD" or null,
  "symptoms": [] list of strings,
  "danger_signs": [] list of strings
}'''
            category_instructions = """
CATEGORY 3: IMMUNIZATION BENEFICIARY REVISIT MANDATORY OBSERVATIONS:
1. Current Weight (kg) -> weight_kg (float e.g. 8.5)
2. Current Height / Length (cm) -> height_cm (float e.g. 68.0)
3. General Health Condition -> general_health_condition ("Good" / "Normal" if healthy, else description)
4. Vaccines Due Today -> vaccines_due_today (string of due vaccine names)
5. Vaccines Given Today -> vaccines_given_today (string of administered vaccine names)
6. Missed Vaccination Doses -> missed_vaccination_doses ("None" if no missed doses, else description)
7. Previous Adverse Events Following Immunization (AEFI) -> previous_aefi ("None reported" if no adverse reaction, else description)
8. Next Vaccination Due Date -> next_vaccination_due_date ("YYYY-MM-DD")
"""

        system_prompt = f"""You are a healthcare data extraction assistant for ASHA workers in India.
Extract structured clinical visit observations from Tamil+English mixed speech transcripts.

RULES:
- Extract ONLY information explicitly stated in the speech.
- NEVER invent clinical values, numbers, or dates.
- Use null for any unmentioned field.
- For negative signs (e.g. "no bleeding", "no headache", "no breathing difficulty", "no missed vaccines"), record "None" or "No".
{category_instructions}

Return ONLY valid JSON matching this exact schema:
{schema}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Beneficiary Category: {b_type}\\nTranscript: {transcript}\\n\\nToday's date is {today}."},
                ],
                max_tokens=1000,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = json.loads(response.choices[0].message.content)
            # Ensure blood_pressure string is synchronized if systolic/diastolic present
            if raw.get("blood_pressure_systolic") and raw.get("blood_pressure_diastolic") and not raw.get("blood_pressure"):
                raw["blood_pressure"] = f"{raw['blood_pressure_systolic']}/{raw['blood_pressure_diastolic']}"

            # Normalize vaginal_bleeding and ifa_calcium_consumption
            if raw.get("vaginal_bleeding"):
                vb = str(raw["vaginal_bleeding"]).lower()
                if any(w in vb for w in ("no", "none", "nil", "clear", "not")):
                    raw["vaginal_bleeding"] = "No"
                elif any(w in vb for w in ("spot", "mild")):
                    raw["vaginal_bleeding"] = "Spotting"
                elif any(w in vb for w in ("yes", "bleed", "present", "heavy", "active")):
                    raw["vaginal_bleeding"] = "Yes"

            if raw.get("ifa_calcium_consumption"):
                ifa = str(raw["ifa_calcium_consumption"]).lower()
                if any(w in ifa for w in ("irregular", "miss", "sometimes", "forgot")):
                    raw["ifa_calcium_consumption"] = "Irregular / Missed Doses"
                elif any(w in ifa for w in ("not", "no", "stopped", "none")):
                    raw["ifa_calcium_consumption"] = "Not Consumed"
                elif any(w in ifa for w in ("only ifa", "iron only")):
                    raw["ifa_calcium_consumption"] = "Only IFA Consumed"
                elif any(w in ifa for w in ("only calcium", "calcium only")):
                    raw["ifa_calcium_consumption"] = "Only Calcium Consumed"
                elif any(w in ifa for w in ("both", "regular", "daily", "yes", "all")):
                    raw["ifa_calcium_consumption"] = "Both Consumed Regularly"

            return raw
        except Exception as e:
            logger.error(f"Revisit clinical extraction failed: {type(e).__name__}")
            raise

    def extract_single_visit_field(self, transcript: str, field: str, category: str = "pregnant_woman") -> dict:
        """
        Extract and normalize a single clinical field from short spoken speech.
        Returns a dict e.g. {"field": field, "value": normalized_value, ...}
        """
        import re
        from services.beneficiary_validation_service import normalize_date_string
        
        t = transcript.strip()
        t_low = t.lower()
        extracted_val = None
        extra = {}

        # 1. Weight (kg)
        if field in ("weight_kg", "current_weight_kg"):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", t)
            if nums:
                extracted_val = float(nums[0])

        # 2. Blood Pressure (mmHg)
        elif field in ("blood_pressure", "bp"):
            bp_match = re.search(r"\b(\d{2,3})\s*(?:/|over|by|-|\s+)\s*(\d{2,3})\b", t, re.I)
            if bp_match:
                sys_val = int(bp_match.group(1))
                dia_val = int(bp_match.group(2))
                extracted_val = f"{sys_val}/{dia_val}"
                extra["blood_pressure_systolic"] = sys_val
                extra["blood_pressure_diastolic"] = dia_val
            else:
                nums = re.findall(r"\b\d{2,3}\b", t)
                if len(nums) >= 2:
                    sys_val, dia_val = int(nums[0]), int(nums[1])
                    extracted_val = f"{sys_val}/{dia_val}"
                    extra["blood_pressure_systolic"] = sys_val
                    extra["blood_pressure_diastolic"] = dia_val

        # 3. Haemoglobin Level (g/dL)
        elif field in ("hb_level", "haemoglobin", "haemoglobin_level"):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", t)
            if nums:
                extracted_val = float(nums[0])

        # 4. Blood Sugar Level (mg/dL)
        elif field in ("blood_sugar_level", "blood_sugar", "sugar_level"):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", t)
            if nums:
                extracted_val = float(nums[0])

        # 5. Vaginal Bleeding (Options: No, Yes, Spotting)
        elif field == "vaginal_bleeding":
            if any(w in t_low for w in ("no", "none", "nil", "false", "nothing", "not", "clear", "normal", "ಇಲ್ಲ", "இல்லை", "नहीं")):
                extracted_val = "No"
            elif any(w in t_low for w in ("spot", "mild", "slight", "little blood")):
                extracted_val = "Spotting"
            elif any(w in t_low for w in ("yes", "bleed", "present", "heavy", "active", "ಹೌದು", "ஆம்", "हाँ")):
                extracted_val = "Yes"
            else:
                extracted_val = "No"

        # 6. Severe Headache or Blurred Vision (Options: No, Yes, Mild Headache)
        elif field in ("severe_headache_blurred_vision", "headache_blurred_vision"):
            if any(w in t_low for w in ("no", "none", "nil", "neither", "nothing", "not", "normal", "fine", "clear", "ಇಲ್ಲ", "இல்லை", "नहीं")):
                extracted_val = "No"
            elif any(w in t_low for w in ("mild", "slight", "little headache")):
                extracted_val = "Mild Headache"
            elif any(w in t_low for w in ("yes", "headache", "blur", "vision", "severe", "dizzy", "pain", "ಹೌದು", "ஆம்", "हाँ")):
                extracted_val = "Yes"
            else:
                extracted_val = "No"

        # 7. Fetal Movement (Options: Normal, Reduced, Absent)
        elif field in ("fetal_movement", "fetal_movements"):
            if any(w in t_low for w in ("absent", "no movement", "stopped", "none", "zero", "not moving")):
                extracted_val = "Absent"
            elif any(w in t_low for w in ("decreas", "reduc", "slow", "less", "sluggish", "ಕಡಿಮೆ", "कम")):
                extracted_val = "Reduced"
            elif any(w in t_low for w in ("normal", "good", "active", "well", "fine", "moving", "kicking", "yes", "ಹೌದು", "हाँ", "ಸಾಮಾನ್ಯ")):
                extracted_val = "Normal"
            else:
                extracted_val = "Normal"

        # 8. IFA and Calcium Tablet Consumption (Options: Both Consumed Regularly, Only IFA Consumed, Only Calcium Consumed, Irregular / Missed Doses, Not Consumed)
        elif field in ("ifa_calcium_consumption", "ifa_calcium", "tablets"):
            if any(w in t_low for w in ("only ifa", "iron only", "ifa only")):
                extracted_val = "Only IFA Consumed"
                extra["ifa_given"] = True
                extra["calcium_given"] = False
            elif any(w in t_low for w in ("only calcium", "calcium only")):
                extracted_val = "Only Calcium Consumed"
                extra["ifa_given"] = False
                extra["calcium_given"] = True
            elif any(w in t_low for w in ("irregular", "miss", "sometimes", "forgot")):
                extracted_val = "Irregular / Missed Doses"
                extra["ifa_given"] = True
                extra["calcium_given"] = True
            elif any(w in t_low for w in ("not", "no", "stopped", "none", "didn't", "left", "ಇಲ್ಲ", "नहीं", "இல்லை")):
                extracted_val = "Not Consumed"
                extra["ifa_given"] = False
                extra["calcium_given"] = False
            elif any(w in t_low for w in ("both", "regular", "daily", "taking", "consumed", "regularly", "yes", "all", "compliant", "ಹೌದು", "हाँ", "ஆம்")):
                extracted_val = "Both Consumed Regularly"
                extra["ifa_given"] = True
                extra["calcium_given"] = True
            else:
                extracted_val = "Both Consumed Regularly"
                extra["ifa_given"] = True
                extra["calcium_given"] = True

        # 9. Body Temperature (°C)
        elif field in ("temperature_celsius", "temperature"):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", t)
            if nums:
                val = float(nums[0])
                if val > 80:  # Fahrenheit
                    val = round((val - 32) * 5 / 9, 1)
                extracted_val = val

        # 10. Respiratory Rate (breaths/min)
        elif field in ("respiratory_rate", "breathing_rate"):
            nums = re.findall(r"\b\d+\b", t)
            if nums:
                extracted_val = int(nums[0])

        # 11. Breastfeeding Status (Options: Exclusive Breastfeeding, Partial Breastfeeding, Formula / Other Milk, Not Breastfeeding)
        elif field == "breastfeeding_status":
            if any(w in t_low for w in ("not", "stopped", "no", "none")):
                extracted_val = "Not Breastfeeding"
            elif any(w in t_low for w in ("formula", "other milk", "bottle", "cow", "powder")):
                extracted_val = "Formula / Other Milk"
            elif any(w in t_low for w in ("partial", "mixed", "some")):
                extracted_val = "Partial Breastfeeding"
            elif any(w in t_low for w in ("exclusive", "only breast", "breastfed", "good latch", "yes", "well")):
                extracted_val = "Exclusive Breastfeeding"
            else:
                extracted_val = "Exclusive Breastfeeding"

        # 12. Difficulty in Feeding (Options: No, Yes)
        elif field in ("difficulty_in_feeding", "feeding_difficulty"):
            if any(w in t_low for w in ("yes", "difficult", "unable", "cannot", "problem", "latch problem")):
                extracted_val = "Yes"
            else:
                extracted_val = "No"

        # 13. Difficulty in Breathing (Options: No, Yes)
        elif field in ("difficulty_in_breathing", "breathing_difficulties"):
            if any(w in t_low for w in ("yes", "fast", "chest", "grunting", "difficult", "stridor")):
                extracted_val = "Yes"
            else:
                extracted_val = "No"

        # 14. Yellowing of Skin or Eyes (Options: No, Yes)
        elif field in ("yellowing_skin_eyes", "jaundice", "jaundice_observations"):
            if any(w in t_low for w in ("yes", "jaundice", "yellow", "yellowing")):
                extracted_val = "Yes"
            else:
                extracted_val = "No"

        # 15. Umbilical Cord Condition (Options: Clean & Dry, Redness / Pus / Foul Smell)
        elif field in ("umbilical_cord_condition", "cord_condition", "cord"):
            if any(w in t_low for w in ("red", "pus", "foul", "smell", "discharge", "infected", "bleeding")):
                extracted_val = "Redness / Pus / Foul Smell"
            else:
                extracted_val = "Clean & Dry"

        # 16. Current Height / Length (cm)
        elif field in ("height_cm", "length_cm", "height"):
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", t)
            if nums:
                extracted_val = float(nums[0])

        # 17. General Health Condition (Options: Good / Active, Fair, Fever / Sick)
        elif field in ("general_health_condition", "health_condition"):
            if any(w in t_low for w in ("fever", "sick", "ill", "poor", "unwell", "danger")):
                extracted_val = "Fever / Sick"
            elif any(w in t_low for w in ("fair", "alert", "moderate", "okay")):
                extracted_val = "Fair"
            elif any(w in t_low for w in ("good", "normal", "healthy", "fine", "active", "well")):
                extracted_val = "Good / Active"
            else:
                extracted_val = "Good / Active"

        # 18-20. Vaccine fields
        elif field in ("vaccines_due_today", "vaccines_given_today"):
            cleaned = re.sub(r"^(vaccine(s)?\s*(due|given)?\s*(are|is)?\s*)", "", t, flags=re.I).strip()
            extracted_val = cleaned or t

        elif field == "missed_vaccination_doses":
            if any(w in t_low for w in ("no", "none", "nil", "nothing", "all given")):
                extracted_val = "None"
            else:
                extracted_val = t

        # 21. Previous AEFI
        elif field in ("previous_aefi", "aefi"):
            if any(w in t_low for w in ("no", "none", "nil", "nothing", "no adverse", "no reaction")):
                extracted_val = "None reported"
            else:
                extracted_val = t

        # 22. Next Vaccination / Visit Date
        elif field in ("next_vaccination_due_date", "next_visit_date", "visit_date"):
            extracted_val = normalize_date_string(t)

        # Fallback to LLM if regex could not extract
        if extracted_val is None:
            try:
                system_prompt = f"You are a medical data extraction assistant. Extract ONLY the value for '{field}' from the speech. Return JSON: {{\"{field}\": <value or null>}}"
                client = self._get_client()
                res = client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Speech: {transcript}"},
                    ],
                    max_tokens=60,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                parsed = json.loads(res.choices[0].message.content)
                extracted_val = parsed.get(field)
            except Exception as e:
                logger.warning(f"Single visit field LLM fallback failed for {field}: {e}")
                extracted_val = transcript

        res_dict = {
            "field": field,
            "value": extracted_val if extracted_val is not None else transcript,
            "raw_transcript": transcript,
            **extra
        }
        return res_dict

    def translate_to_english(self, transcript: str, source_language: str) -> str:
        """Translate non-English transcript to English."""
        if not source_language or source_language == 'en' or not transcript.strip():
            return transcript
        system_prompt = (
            "You are a medical translator for ASHA healthcare workers in India. "
            "Translate the following healthcare speech transcript into clear, fluent English. "
            "Preserve all patient names, numbers, ages, dates, locations, and clinical terms accurately. "
            "Return ONLY the English translation without any thoughts, preamble, or notes."
        )
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
                max_tokens=2048,
                temperature=0.1,
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                return content
            logger.warning("Empty content returned from translation LLM; keeping original transcript.")
            return transcript
        except Exception as e:
            logger.error(f"Translation failed: {type(e).__name__}: {e}")
            return transcript



# Singleton
groq_service = GroqService()
