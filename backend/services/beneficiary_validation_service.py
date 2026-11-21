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
            missing.append("age")
        else:
            try:
                age_val = int(age)
                if not (10 <= age_val <= 60):
                    errors.append(f"Age {age_val} is outside standard maternal range (10-60).")
                sanitized["age"] = age_val
            except (ValueError, TypeError):
                errors.append("Age must be a valid integer.")

        # Address / Household ID
        addr = str(sanitized.get("address") or sanitized.get("household") or sanitized.get("village") or "").strip()
        if not addr:
            missing.append("address")

        # Pregnancy registration status
        reg_status = sanitized.get("pregnancy_registration_status")
        if not reg_status or str(reg_status).strip() in ("", "null", "None"):
            # Registration workflow default
            sanitized["pregnancy_registration_status"] = "registered"
        else:
            sanitized["pregnancy_registration_status"] = str(reg_status).strip()

        # LMP
        lmp_raw = sanitized.get("lmp")
        if not lmp_raw:
            missing.append("lmp")
        else:
            norm_lmp = normalize_date_string(str(lmp_raw))
            if not norm_lmp:
                errors.append(f"LMP date '{lmp_raw}' is invalid. Format must be YYYY-MM-DD.")
            else:
                sanitized["lmp"] = norm_lmp

        # EDD
        edd_raw = sanitized.get("edd") or sanitized.get("expected_delivery_date")
        if not edd_raw:
            missing.append("edd")
        else:
            norm_edd = normalize_date_string(str(edd_raw), default_year=datetime.now().year + 1)
            if not norm_edd:
                errors.append(f"EDD date '{edd_raw}' is invalid. Format must be YYYY-MM-DD.")
            else:
                sanitized["edd"] = norm_edd
                sanitized["expected_delivery_date"] = norm_edd

        # Consistency check: LMP vs EDD
        if sanitized.get("lmp") and sanitized.get("edd"):
            d_lmp = _parse_date(sanitized["lmp"])
            d_edd = _parse_date(sanitized["edd"])
            if d_lmp and d_edd:
                diff_days = (d_edd - d_lmp).days
                if diff_days <= 0:
                    errors.append(f"EDD ({sanitized['edd']}) cannot be on or before LMP ({sanitized['lmp']}).")
                elif abs(diff_days - 280) > 42:  # More than 6 weeks deviation from standard 40 weeks
                    inconsistencies.append(
                        f"LMP ({sanitized['lmp']}) and EDD ({sanitized['edd']}) differ by {diff_days} days (standard full-term gestation is ~280 days)."
                    )

        # Gestational age in weeks
        ga = sanitized.get("gestational_age_weeks") or sanitized.get("pregnancy_month")
        if ga in (None, ""):
            # Estimate from LMP if available
            if sanitized.get("lmp") and _parse_date(sanitized["lmp"]):
                d_lmp = _parse_date(sanitized["lmp"])
                weeks_est = max(1, (date.today() - d_lmp).days // 7)
                if 1 <= weeks_est <= 44:
                    sanitized["gestational_age_weeks"] = weeks_est
                else:
                    missing.append("gestational_age_weeks")
            else:
                missing.append("gestational_age_weeks")
        else:
            try:
                ga_val = int(ga)
                # If given as month (1-9), convert to weeks estimate
                if sanitized.get("gestational_age_weeks") is None and sanitized.get("pregnancy_month"):
                    pm = int(sanitized["pregnancy_month"])
                    sanitized["gestational_age_weeks"] = pm * 4
                else:
                    if not (1 <= ga_val <= 44):
                        errors.append(f"Gestational age {ga_val} weeks is outside valid range (1-44).")
                    sanitized["gestational_age_weeks"] = ga_val
            except (ValueError, TypeError):
                errors.append("Gestational age must be an integer.")

        # Gravida (number of previous pregnancies)
        gravida = sanitized.get("gravida")
        if gravida in (None, ""):
            # Check if previous_pregnancies is provided
            if sanitized.get("previous_pregnancies") is not None:
                gravida = sanitized.get("previous_pregnancies")
                sanitized["gravida"] = gravida
            else:
                missing.append("gravida")
        
        if gravida not in (None, ""):
            try:
                g_val = int(gravida)
                if g_val < 0:
                    errors.append("Number of previous pregnancies cannot be negative.")
                sanitized["gravida"] = g_val
            except (ValueError, TypeError):
                errors.append("Gravida must be a valid integer.")

        # Previous live births
        plb = sanitized.get("previous_live_births")
        if plb in (None, ""):
            missing.append("previous_live_births")
        else:
            try:
                plb_val = int(plb)
                if plb_val < 0:
                    errors.append("Previous live births cannot be negative.")
                sanitized["previous_live_births"] = plb_val
                if "gravida" in sanitized and isinstance(sanitized["gravida"], int):
                    if plb_val > sanitized["gravida"]:
                        errors.append("Previous live births cannot exceed the number of previous pregnancies.")
            except (ValueError, TypeError):
                errors.append("Previous live births must be a valid integer.")

        # Previous pregnancy complications
        comp = sanitized.get("previous_complications")
        if comp in (None, ""):
            # If gravida is 0 (first pregnancy) or no previous live births, default to "None reported"
            if sanitized.get("gravida") == 0 or sanitized.get("previous_live_births") == 0:
                sanitized["previous_complications"] = "None reported"
            else:
                missing.append("previous_complications")
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
            missing.append("name")
        else:
            sanitized["name"] = name
            sanitized["baby_name"] = name

        dob_raw = sanitized.get("dob") or sanitized.get("date_of_birth")
        if not dob_raw:
            missing.append("dob")
        else:
            norm_dob = normalize_date_string(str(dob_raw))
            if not norm_dob:
                errors.append(f"Date of birth '{dob_raw}' is invalid. Format must be YYYY-MM-DD.")
            else:
                sanitized["dob"] = norm_dob

        gender = str(sanitized.get("gender") or "").strip().lower()
        if not gender:
            missing.append("gender")
        elif gender not in ("male", "female", "other"):
            errors.append(f"Gender '{gender}' is invalid. Allowed: male, female, other.")
        else:
            sanitized["gender"] = gender

        # Maternal reference: mother_beneficiary_id OR mother_name
        mother_id = str(sanitized.get("mother_beneficiary_id") or "").strip().upper()
        mother_name = str(sanitized.get("mother_name") or "").strip()

        if not mother_id and not mother_name:
            missing.append("maternal_reference")
        else:
            if mother_id:
                sanitized["mother_beneficiary_id"] = mother_id
                if check_mother_exists:
                    mother = mongodb_service.find_one("beneficiaries", {
                        "beneficiary_id": mother_id,
                        "is_deleted": {"$ne": True}
                    })
                    if not mother:
                        errors.append(f"Mother's Beneficiary ID '{mother_id}' does not exist in the database.")
                    elif not mother_name:
                        sanitized["mother_name"] = mother.get("name", "")

            if mother_name:
                sanitized["mother_name"] = mother_name

        # Place of delivery
        pod = str(sanitized.get("place_of_delivery") or "").strip()
        if not pod:
            missing.append("place_of_delivery")
        else:
            sanitized["place_of_delivery"] = pod

        # Birth weight
        bw = sanitized.get("birth_weight_kg") or sanitized.get("birth_weight")
        if bw in (None, ""):
            missing.append("birth_weight_kg")
        else:
            try:
                bw_val = float(bw)
                if not (0.4 <= bw_val <= 10.0):
                    errors.append(f"Birth weight {bw_val} kg is outside valid range (0.4 - 10.0 kg).")
                sanitized["birth_weight_kg"] = round(bw_val, 2)
            except (ValueError, TypeError):
                errors.append("Birth weight must be a valid number.")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. IMMUNIZATION / CHILD
    # ─────────────────────────────────────────────────────────────────────────
    elif category == "immunization_child":
        name = str(sanitized.get("name") or sanitized.get("child_name") or "").strip()
        if not name:
            missing.append("name")
        else:
            sanitized["name"] = name
            sanitized["child_name"] = name

        dob_raw = sanitized.get("dob") or sanitized.get("date_of_birth")
        if not dob_raw:
            missing.append("dob")
        else:
            norm_dob = normalize_date_string(str(dob_raw))
            if not norm_dob:
                errors.append(f"Date of birth '{dob_raw}' is invalid. Format must be YYYY-MM-DD.")
            else:
                sanitized["dob"] = norm_dob

        gender = str(sanitized.get("gender") or "").strip().lower()
        if not gender:
            missing.append("gender")
        elif gender not in ("male", "female", "other"):
            errors.append(f"Gender '{gender}' is invalid. Allowed: male, female, other.")
        else:
            sanitized["gender"] = gender

        # Maternal reference
        mother_id = str(sanitized.get("mother_beneficiary_id") or "").strip().upper()
        mother_name = str(sanitized.get("mother_name") or "").strip()

        if not mother_id and not mother_name:
            missing.append("maternal_reference")
        else:
            if mother_id:
                sanitized["mother_beneficiary_id"] = mother_id
                if check_mother_exists:
                    mother = mongodb_service.find_one("beneficiaries", {
                        "beneficiary_id": mother_id,
                        "is_deleted": {"$ne": True}
                    })
                    if not mother:
                        errors.append(f"Mother's Beneficiary ID '{mother_id}' does not exist in the database.")
                    elif not mother_name:
                        sanitized["mother_name"] = mother.get("name", "")
            if mother_name:
                sanitized["mother_name"] = mother_name

        # Immunization card status
        card_status = str(sanitized.get("immunization_card_status") or "").strip().lower()
        if not card_status or card_status in ("null", "none"):
            missing.append("immunization_card_status")
        elif card_status not in ("yes", "no", "unknown", "available", "unavailable"):
            errors.append(f"Card status '{card_status}' invalid. Allowed: yes, no, unknown.")
        else:
            sanitized["immunization_card_status"] = "yes" if card_status in ("yes", "available") else ("no" if card_status in ("no", "unavailable") else "unknown")

        # Vaccination status
        vac_status = sanitized.get("vaccination_status")
        if not vac_status or vac_status in ("", "null", "None", []):
            missing.append("vaccination_status")
        else:
            # Can be structured or string representation
            sanitized["vaccination_status"] = vac_status

    # ─────────────────────────────────────────────────────────────────────────
    # 4. OTHER BENEFICIARY
    # ─────────────────────────────────────────────────────────────────────────
    elif category == "other":
        name = str(sanitized.get("name") or "").strip()
        if not name:
            missing.append("name")

        phone = str(sanitized.get("phone") or "").strip()
        if not phone:
            missing.append("phone")
        elif not _is_valid_indian_phone(phone):
            errors.append(f"Phone number '{phone}' must be a valid 10-digit Indian mobile number.")
        else:
            sanitized["phone"] = re.sub(r"[^\d]", "", phone)

        b_cat = str(sanitized.get("beneficiary_category") or "").strip()
        if not b_cat:
            missing.append("beneficiary_category")
        else:
            sanitized["beneficiary_category"] = b_cat

        addr = str(sanitized.get("address") or sanitized.get("village") or "").strip()
        if not addr:
            missing.append("address")

        em_contact = str(sanitized.get("emergency_contact") or sanitized.get("alternate_contact") or "").strip()
        if not em_contact:
            missing.append("emergency_contact")
        else:
            sanitized["emergency_contact"] = em_contact

        bg = str(sanitized.get("blood_group") or "").strip().upper()
        if not bg:
            missing.append("blood_group")
        elif bg not in [b.upper() for b in BLOOD_GROUPS]:
            errors.append(f"Blood group '{bg}' is invalid. Allowed: {', '.join(BLOOD_GROUPS)}")
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
