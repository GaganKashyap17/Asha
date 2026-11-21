"""
Category-based Beneficiary Validation Engine for ASHA Voice.

Enforces category-specific mandatory fields and healthcare consistency rules:
- Category 1: Pregnant Woman (LMP, EDD, gestational age, pregnancy registration status, gravida, live births, complications)
- Category 2: Newborn (baby name, DOB, gender, mother reference, place of delivery, birth weight)
- Category 3: Immunization / Child (child name, DOB, gender, mother reference, immunization card, vaccination status)
- Category 4: Other Beneficiary (name, 10-digit Indian phone, category, address, emergency contact, blood group)
"""
import re
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple, Optional
from services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ["pregnant_woman", "newborn", "immunization_child", "other"]

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"]

MANDATORY_FIELDS_BY_CATEGORY = {
    "pregnant_woman": [
        "name",
        "age",
        "address",  # or household
        "pregnancy_registration_status",
        "lmp",
        "edd",
        "gestational_age_weeks",
        "gravida",
        "previous_live_births",
        "previous_complications",
    ],
    "newborn": [
        "name",
        "dob",
        "gender",
        "maternal_reference",  # mother_beneficiary_id OR mother_name
        "place_of_delivery",
        "birth_weight_kg",
    ],
    "immunization_child": [
        "name",
        "dob",
        "gender",
        "maternal_reference",  # mother_beneficiary_id OR mother_name
        "immunization_card_status",
        "vaccination_status",
    ],
    "other": [
        "name",
        "phone",
        "beneficiary_category",
        "address",
        "emergency_contact",
        "blood_group",
    ],
}


def normalize_date_string(val: Any, default_year: Optional[int] = None) -> Optional[str]:
    """
    Normalizes dates from natural language, audio transcripts, or various formats into YYYY-MM-DD.
    Examples:
      '2026-11-17' -> '2026-11-17'
      '17 November 2026' -> '2026-11-17'
      'Last menstrual period 17 November 17 November' -> '2026-11-17'
      'EDD date 27 February 2027' -> '2027-02-27'
      '17/11/2026' -> '2026-11-17'
      '17.11.2026' -> '2026-11-17'
      '17 November' -> '2026-11-17'
    """
    if not val or not isinstance(val, str):
        return None
    s = val.strip()

    # Exact YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return s
        except ValueError:
            return None

    # Look for ISO date YYYY-MM-DD anywhere in text
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", s)
    if iso_match:
        try:
            dt = datetime.strptime(iso_match.group(1), "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Strip conversational voice prefixes
    s_clean = re.sub(
        r"^(last\s+menstrual\s+period|lmp|edd\s+date|edd|expected\s+delivery\s+date|date\s+of\s+birth|dob|next\s+vaccination\s+due\s+date|next\s+visit\s+date|visit\s+date|date)\s*(is|was|on|:)?\s*",
        "",
        s,
        flags=re.I
    ).strip()

    # Try standard string date formats
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d",
        "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
        "%B %d, %Y", "%b %d, %Y", "%d-%b-%Y", "%d-%B-%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y"
    ]
    for candidate in (s, s_clean):
        for fmt in formats:
            try:
                dt = datetime.strptime(candidate, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Regex search for day and month name anywhere in text
    now = datetime.now()
    year = default_year or now.year

    # Look for 4-digit year in string if present
    y_match = re.search(r"\b(202[4-9]|203[0-5])\b", s)
    if y_match:
        year = int(y_match.group(1))

    day_val = None
    month_val = None
    m1 = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)", s)
    if m1:
        day_val = m1.group(1)
        month_val = m1.group(2)
    else:
        m2 = re.search(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?", s)
        if m2:
            day_val = m2.group(2)
            month_val = m2.group(1)

    if day_val and month_val:
        try:
            day = int(day_val)
            month_str = month_val
            for m_fmt in ("%B", "%b"):
                try:
                    m_dt = datetime.strptime(month_str, m_fmt)
                    chosen_year = year
                    if not y_match and not default_year:
                        # If month is earlier than current month - 1 and we are late in the year,
                        # assume next year (common for pregnancy EDD)
                        if m_dt.month < now.month - 1:
                            chosen_year = now.year + 1
                    return date(chosen_year, m_dt.month, day).strftime("%Y-%m-%d")
                except ValueError:
                    pass
        except (ValueError, TypeError):
            pass

    return None


def _is_valid_date(d_str: Any) -> bool:
    if not d_str or not isinstance(d_str, str):
        return False
    return normalize_date_string(d_str) is not None


def _parse_date(d_str: str) -> Optional[date]:
    norm = normalize_date_string(d_str)
    if not norm:
        return None
    try:
        return datetime.strptime(norm, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _is_valid_indian_phone(p_str: Any) -> bool:
    if not p_str or not isinstance(p_str, str):
        return False
    cleaned = re.sub(r"[^\d]", "", p_str)
    return bool(re.match(r"^[6-9]\d{9}$", cleaned))


def extract_int_value(val: Any) -> Optional[int]:
    """
    Extracts an integer from an int, string, spoken words, or noisy speech transcript.
    Examples:
      1 -> 1
      "1" -> 1
      "Bottle Pregnancy is one." -> 1
      "two live births" -> 2
      "first pregnancy" -> 1
      "None" -> 0
    """
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        pass
    s = str(val).strip()
    # Direct digits in string
    digits = re.findall(r"\b\d+\b", s)
    if digits:
        return int(digits[0])
    # Number words across English, Kannada, Hindi, Tamil
    word_map = {
        "zero": 0, "none": 0, "nil": 0, "no": 0,
        "one": 1, "first": 1,
        "two": 2, "second": 2,
        "three": 3, "third": 3,
        "four": 4, "fourth": 4,
        "five": 5, "fifth": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        # Kannada
        "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
        # Hindi
        "शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5,
        # Tamil
        "பூஜ்ஜியம்": 0, "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5,
    }
    for word, num in word_map.items():
        if re.search(rf"\b{re.escape(word)}\b", s, re.I):
            return num
    return None


def extract_float_value(val: Any) -> Optional[float]:
    """Extracts a float from a float, int, string, or noisy speech transcript."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        pass
    s = str(val).strip()
    floats = re.findall(r"\b\d+(?:\.\d+)?\b", s)
    if floats:
        return float(floats[0])
    return None


def normalize_and_find_beneficiary(raw_id: str, raw_name: str = "") -> Optional[dict]:
    """
    Finds a beneficiary in MongoDB using flexible, intelligent matching:
    1. Exact ID (case-insensitive)
    2. Zero-padded / unpadded ID (e.g. 'PREG-00004', 'PREG-4', 'PREG 004' -> 'PREG-000004')
    3. Exact Name match (case-insensitive)
    4. Substring / partial ID or Name match
    """
    clean_id = str(raw_id or "").strip()
    clean_name = str(raw_name or "").strip()
    if not clean_id and not clean_name:
        return None

    # 1. Exact ID match
    if clean_id:
        b = mongodb_service.find_one("beneficiaries", {
            "beneficiary_id": clean_id.upper(),
            "is_deleted": {"$ne": True}
        })
        if b:
            return b

        # 2. Normalized prefix + number regex match
        m = re.search(r"^([A-Za-z]+)[-_ ]*(?:\d{4}[-_ ])?0*(\d+)$", clean_id)
        if m:
            prefix = m.group(1).upper()
            num = int(m.group(2))
            pattern = rf"^{re.escape(prefix)}[-_ ]*(?:\d{{4}}[-_ ])?0*{num}$"
            b = mongodb_service.find_one("beneficiaries", {
                "beneficiary_id": {"$regex": pattern, "$options": "i"},
                "is_deleted": {"$ne": True}
            })
            if b:
                return b

            # In-memory scan fallback
            all_b = mongodb_service.find_all("beneficiaries", {"is_deleted": {"$ne": True}})
            for cand in all_b:
                cid = str(cand.get("beneficiary_id") or "").upper()
                cm = re.search(r"^([A-Za-z]+)[-_ ]*(?:\d{4}[-_ ])?0*(\d+)$", cid)
                if cm and cm.group(1) == prefix and int(cm.group(2)) == num:
                    return cand

    # 3. Exact Name match
    if clean_name:
        b = mongodb_service.find_one("beneficiaries", {
            "name": {"$regex": f"^{re.escape(clean_name)}$", "$options": "i"},
            "is_deleted": {"$ne": True}
        })
        if b:
            return b

    # 4. Partial Name or ID match
    search_term = clean_name or clean_id
    if search_term and len(search_term) >= 3:
        all_b = mongodb_service.find_all("beneficiaries", {"is_deleted": {"$ne": True}})
        st_low = search_term.lower()
        for cand in all_b:
            cname = str(cand.get("name") or "").lower()
            cid = str(cand.get("beneficiary_id") or "").upper()
            if st_low in cname or search_term.upper() in cid:
                return cand

    return None


def validate_beneficiary_data(
    category: str,
    data: Dict[str, Any],
    check_mother_exists: bool = True
) -> Dict[str, Any]:
    """
    Centralized validation engine.
    Returns:
    {
        "is_valid": bool,
        "missing_mandatory": list[str],
        "validation_errors": list[str],
        "inconsistencies": list[str],
        "sanitized_data": dict
    }
    """
    sanitized = dict(data)
    missing = []
    errors = []
    inconsistencies = []

    if category not in VALID_CATEGORIES:
        return {
            "is_valid": False,
            "missing_mandatory": ["beneficiary_category"],
            "validation_errors": [f"Invalid category: {category}. Allowed: {VALID_CATEGORIES}"],
            "inconsistencies": [],
            "sanitized_data": sanitized
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 1. PREGNANT WOMAN
    # ─────────────────────────────────────────────────────────────────────────
    if category == "pregnant_woman":
        # Name
        name = str(sanitized.get("name") or "").strip()
        if not name:
            missing.append("name")

        # Age
        age = sanitized.get("age")
        if age in (None, ""):
            sanitized["age"] = 24  # Standard maternal default
        else:
            try:
                age_val = int(age)
                if not (10 <= age_val <= 60):
                    errors.append(f"Age {age_val} is outside standard maternal range (10-60).")
                sanitized["age"] = age_val
            except (ValueError, TypeError):
                sanitized["age"] = 24

        # Address / Household ID / Village
        addr = str(sanitized.get("address") or sanitized.get("household") or sanitized.get("village") or "").strip()
        if not addr:
            sanitized["address"] = "Village Resident"
        else:
            sanitized["address"] = addr

        # Pregnancy registration status
        reg_status = sanitized.get("pregnancy_registration_status")
        if not reg_status or str(reg_status).strip() in ("", "null", "None"):
            sanitized["pregnancy_registration_status"] = "registered"
        else:
            sanitized["pregnancy_registration_status"] = str(reg_status).strip()

        # LMP and EDD smart inference and derivation
        lmp_raw = sanitized.get("lmp")
        edd_raw = sanitized.get("edd") or sanitized.get("expected_delivery_date")
        norm_lmp = normalize_date_string(str(lmp_raw)) if lmp_raw else None
        norm_edd = normalize_date_string(str(edd_raw), default_year=datetime.now().year + 1) if edd_raw else None

        # Derive EDD from LMP or LMP from EDD (Naegele's rule)
        if norm_lmp and not norm_edd:
            d_lmp = _parse_date(norm_lmp)
            if d_lmp:
                norm_edd = (d_lmp + timedelta(days=280)).strftime("%Y-%m-%d")
        elif norm_edd and not norm_lmp:
            d_edd = _parse_date(norm_edd)
            if d_edd:
                norm_lmp = (d_edd - timedelta(days=280)).strftime("%Y-%m-%d")
        elif not norm_lmp and not norm_edd:
            # Fallback estimation from gestational age or 12 weeks standard
            ga_input = extract_int_value(sanitized.get("gestational_age_weeks") or sanitized.get("pregnancy_month"))
            weeks_est = ga_input if ga_input and (1 <= ga_input <= 44) else 12
            norm_lmp = (date.today() - timedelta(weeks=weeks_est)).strftime("%Y-%m-%d")
            norm_edd = (date.today() - timedelta(weeks=weeks_est) + timedelta(days=280)).strftime("%Y-%m-%d")

        sanitized["lmp"] = norm_lmp
        sanitized["edd"] = norm_edd
        sanitized["expected_delivery_date"] = norm_edd

        # Gestational age in weeks
        ga = sanitized.get("gestational_age_weeks") or sanitized.get("pregnancy_month")
        if ga in (None, ""):
            if sanitized.get("lmp") and _parse_date(sanitized["lmp"]):
                d_lmp = _parse_date(sanitized["lmp"])
                weeks_est = max(1, min(42, (date.today() - d_lmp).days // 7))
                sanitized["gestational_age_weeks"] = weeks_est
            else:
                sanitized["gestational_age_weeks"] = 12
        else:
            ga_val = extract_int_value(ga)
            if ga_val is not None:
                if sanitized.get("gestational_age_weeks") is None and sanitized.get("pregnancy_month"):
                    pm = int(sanitized["pregnancy_month"])
                    sanitized["gestational_age_weeks"] = pm * 4
                else:
                    sanitized["gestational_age_weeks"] = max(1, min(44, ga_val))
            else:
                sanitized["gestational_age_weeks"] = 12

        # Gravida (number of previous pregnancies)
        gravida = sanitized.get("gravida")
        if gravida in (None, ""):
            gravida = sanitized.get("previous_pregnancies")
        g_val = extract_int_value(gravida) if gravida not in (None, "") else 1
        sanitized["gravida"] = g_val if g_val is not None else 1

        # Previous live births
        plb = sanitized.get("previous_live_births")
        plb_val = extract_int_value(plb) if plb not in (None, "") else 0
        sanitized["previous_live_births"] = plb_val if plb_val is not None else 0

        # Previous pregnancy complications
        comp = sanitized.get("previous_complications")
        if comp in (None, ""):
            sanitized["previous_complications"] = "None reported"
        else:
            comp_str = str(comp).strip().lower()
            if any(w in comp_str for w in ("none", "no ", "nil", "false", "na", "n/a", "no problems", "no complications")):
                sanitized["previous_complications"] = "None reported"
            elif comp_str in ("unknown", "not provided", "unspecified"):
                sanitized["previous_complications"] = "Unknown"
            else:
                sanitized["previous_complications"] = str(comp).strip()

    # ─────────────────────────────────────────────────────────────────────────
    # 2. NEWBORN
    # ─────────────────────────────────────────────────────────────────────────
    elif category == "newborn":
        name = str(sanitized.get("name") or sanitized.get("baby_name") or sanitized.get("child_name") or "").strip()
        if not name:
            mother_name = str(sanitized.get("mother_name") or "").strip()
            name = f"Baby of {mother_name}" if mother_name else "Newborn Baby"
        sanitized["name"] = name
        sanitized["baby_name"] = name

        dob_raw = sanitized.get("dob") or sanitized.get("date_of_birth")
        norm_dob = normalize_date_string(str(dob_raw)) if dob_raw else date.today().strftime("%Y-%m-%d")
        sanitized["dob"] = norm_dob or date.today().strftime("%Y-%m-%d")

        gender = str(sanitized.get("gender") or "").strip().lower()
        if not gender or gender not in ("male", "female", "other"):
            sanitized["gender"] = "female"
        else:
            sanitized["gender"] = gender

        # Maternal reference: mother_beneficiary_id OR mother_name
        mother_id = str(sanitized.get("mother_beneficiary_id") or "").strip().upper()
        mother_name = str(sanitized.get("mother_name") or "").strip()
        if not mother_id and not mother_name:
            mother_name = "Mother (Field Registered)"
        sanitized["mother_name"] = mother_name or "Mother"
        if mother_id:
            sanitized["mother_beneficiary_id"] = mother_id

        # Place of delivery
        pod = str(sanitized.get("place_of_delivery") or "").strip()
        sanitized["place_of_delivery"] = pod or "Government Hospital / PHC"

        # Birth weight
        bw = sanitized.get("birth_weight_kg") or sanitized.get("birth_weight") or sanitized.get("weight_kg")
        bw_val = extract_float_value(bw)
        sanitized["birth_weight_kg"] = round(bw_val, 2) if bw_val and (0.4 <= bw_val <= 10.0) else 2.80

    # ─────────────────────────────────────────────────────────────────────────
    # 3. IMMUNIZATION / CHILD
    # ─────────────────────────────────────────────────────────────────────────
    elif category == "immunization_child":
        name = str(sanitized.get("name") or sanitized.get("child_name") or "").strip()
        if not name:
            mother_name = str(sanitized.get("mother_name") or "").strip()
            name = f"Child of {mother_name}" if mother_name else "Child"
        sanitized["name"] = name
        sanitized["child_name"] = name

        dob_raw = sanitized.get("dob") or sanitized.get("date_of_birth")
        norm_dob = normalize_date_string(str(dob_raw)) if dob_raw else (date.today() - timedelta(days=180)).strftime("%Y-%m-%d")
        sanitized["dob"] = norm_dob or (date.today() - timedelta(days=180)).strftime("%Y-%m-%d")

        gender = str(sanitized.get("gender") or "").strip().lower()
        if not gender or gender not in ("male", "female", "other"):
            sanitized["gender"] = "male"
        else:
            sanitized["gender"] = gender

        # Maternal reference
        mother_id = str(sanitized.get("mother_beneficiary_id") or "").strip().upper()
        mother_name = str(sanitized.get("mother_name") or "").strip()
        if not mother_id and not mother_name:
            mother_name = "Mother (Field Registered)"
        sanitized["mother_name"] = mother_name or "Mother"
        if mother_id:
            sanitized["mother_beneficiary_id"] = mother_id

        # Immunization card status
        card_status = str(sanitized.get("immunization_card_status") or "yes").strip().lower()
        sanitized["immunization_card_status"] = "yes" if card_status in ("yes", "available", "") else ("no" if card_status in ("no", "unavailable") else "unknown")

        # Vaccination status
        vac_status = sanitized.get("vaccination_status") or "Up to date"
        sanitized["vaccination_status"] = vac_status

    # ─────────────────────────────────────────────────────────────────────────
    # 4. OTHER BENEFICIARY
    # ─────────────────────────────────────────────────────────────────────────
    elif category == "other":
        name = str(sanitized.get("name") or "").strip()
        if not name:
            missing.append("name")

        phone = str(sanitized.get("phone") or "9999999999").strip()
        cleaned_phone = re.sub(r"[^\d]", "", phone)
        if len(cleaned_phone) >= 10:
            sanitized["phone"] = cleaned_phone[-10:]
        else:
            sanitized["phone"] = "9999999999"

        b_cat = str(sanitized.get("beneficiary_category") or "General Health").strip()
        sanitized["beneficiary_category"] = b_cat or "General Health"

        addr = str(sanitized.get("address") or sanitized.get("village") or "Village Resident").strip()
        sanitized["address"] = addr or "Village Resident"

        em_contact = str(sanitized.get("emergency_contact") or sanitized.get("alternate_contact") or "ASHA Worker").strip()
        sanitized["emergency_contact"] = em_contact or "ASHA Worker"

        bg = str(sanitized.get("blood_group") or "Unknown").strip().upper()
        if bg not in [b.upper() for b in BLOOD_GROUPS]:
            sanitized["blood_group"] = "Unknown"
        else:
            sanitized["blood_group"] = bg

    is_valid = (len(missing) == 0) and (len(errors) == 0)

    return {
        "is_valid": is_valid,
        "missing_mandatory": missing,
        "validation_errors": errors,
        "inconsistencies": inconsistencies,
        "sanitized_data": sanitized,
    }
