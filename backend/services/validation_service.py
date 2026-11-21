"""
Validation service — business-rule validation for ASHA Voice visit records.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


MANDATORY_FIELDS: Dict[str, List[str]] = {
    "pregnancy":    ["beneficiary_name", "visit_type", "pregnancy_month", "weight_kg"],
    "newborn":      ["beneficiary_name", "visit_type", "weight_kg"],
    "postnatal":    ["beneficiary_name", "visit_type", "weight_kg"],
    "immunisation": ["beneficiary_name", "visit_type", "vaccinations"],
    "household":    ["beneficiary_name", "visit_type"],
}

# 8 Category-Specific Mandatory Fields for Revisit Visits
REVISIT_MANDATORY_FIELDS: Dict[str, List[str]] = {
    "pregnant_woman": [
        "weight_kg",
        "blood_pressure",
        "hb_level",
        "blood_sugar_level",
        "vaginal_bleeding",
        "severe_headache_blurred_vision",
        "fetal_movement",
        "ifa_calcium_consumption",
    ],
    "pregnancy": [
        "weight_kg",
        "blood_pressure",
        "hb_level",
        "blood_sugar_level",
        "vaginal_bleeding",
        "severe_headache_blurred_vision",
        "fetal_movement",
        "ifa_calcium_consumption",
    ],
    "newborn": [
        "weight_kg",
        "temperature_celsius",
        "respiratory_rate",
        "breastfeeding_status",
        "difficulty_in_feeding",
        "difficulty_in_breathing",
        "yellowing_skin_eyes",
        "umbilical_cord_condition",
    ],
    "immunization_child": [
        "weight_kg",
        "height_cm",
        "general_health_condition",
        "vaccines_due_today",
        "vaccines_given_today",
        "missed_vaccination_doses",
        "previous_aefi",
        "next_vaccination_due_date",
    ],
    "immunisation": [
        "weight_kg",
        "height_cm",
        "general_health_condition",
        "vaccines_due_today",
        "vaccines_given_today",
        "missed_vaccination_doses",
        "previous_aefi",
        "next_vaccination_due_date",
    ],
}

FIELD_LABELS: Dict[str, str] = {
    "beneficiary_name":               "the beneficiary's name",
    "visit_type":                     "the visit type",
    "pregnancy_month":                "the pregnancy month (1 through 9)",
    "weight_kg":                      "Current Weight (kg)",
    "vaccinations":                   "vaccinations given",
    "visit_date":                     "visit date",
    "next_visit_date":                "next visit date",
    "anc_completed":                  "whether ANC checkup was completed",
    "ifa_given":                      "whether IFA tablet was given",
    # Pregnant Woman Revisit
    "blood_pressure":                 "Blood Pressure (mmHg)",
    "hb_level":                       "Haemoglobin Level (g/dL)",
    "blood_sugar_level":              "Blood Sugar Level (mg/dL)",
    "vaginal_bleeding":               "Vaginal Bleeding observation",
    "severe_headache_blurred_vision": "Severe Headache or Blurred Vision observation",
    "fetal_movement":                 "Fetal Movement status",
    "ifa_calcium_consumption":        "IFA and Calcium Tablet Consumption",
    # Newborn Revisit
    "temperature_celsius":            "Body Temperature (°C)",
    "respiratory_rate":               "Respiratory Rate (breaths/min)",
    "breastfeeding_status":           "Breastfeeding Status",
    "difficulty_in_feeding":          "Difficulty in Feeding observation",
    "difficulty_in_breathing":        "Difficulty in Breathing observation",
    "yellowing_skin_eyes":            "Yellowing of Skin or Eyes observation",
    "umbilical_cord_condition":       "Umbilical Cord Condition",
    # Immunization Revisit
    "height_cm":                      "Current Height / Length (cm)",
    "general_health_condition":       "General Health Condition",
    "vaccines_due_today":             "Vaccines Due Today",
    "vaccines_given_today":           "Vaccines Given Today",
    "missed_vaccination_doses":       "Missed Vaccination Doses",
    "previous_aefi":                  "Previous AEFI (Adverse Events Following Immunization)",
    "next_vaccination_due_date":      "Next Vaccination Due Date",
}

VALID_VISIT_TYPES = {"pregnancy", "newborn", "postnatal", "immunisation", "household"}

WEIGHT_MIN_KG = 0.5
WEIGHT_MAX_KG = 200.0


class ValidationService:
    """Validates extracted visit data against ASHA program business rules."""

    def get_mandatory_fields(self, visit_type: str, category: Optional[str] = None) -> List[str]:
        if category and category in REVISIT_MANDATORY_FIELDS:
            return REVISIT_MANDATORY_FIELDS[category]
        return MANDATORY_FIELDS.get(visit_type, MANDATORY_FIELDS.get("household", []))

    def get_missing_mandatory_fields(self, record: dict, category: Optional[str] = None) -> List[str]:
        cat = category or record.get("revisit_category")
        visit_type = record.get("visit_type", "household")
        
        # Check if record has a revisit category
        if cat and cat in REVISIT_MANDATORY_FIELDS:
            mandatory = REVISIT_MANDATORY_FIELDS[cat]
        else:
            mandatory = self.get_mandatory_fields(visit_type)

        missing = []
        for field in mandatory:
            # Special aliases / composite checks
            if field == "blood_pressure":
                bp = record.get("blood_pressure")
                sys = record.get("blood_pressure_systolic")
                dia = record.get("blood_pressure_diastolic")
                if self._is_missing(bp) and (self._is_missing(sys) or self._is_missing(dia)):
                    missing.append("blood_pressure")
                continue

            if field == "ifa_calcium_consumption":
                ifc = record.get("ifa_calcium_consumption")
                ifa = record.get("ifa_given")
                calc = record.get("calcium_given")
                if self._is_missing(ifc) and ifa is None and calc is None:
                    missing.append("ifa_calcium_consumption")
                continue

            if field == "next_vaccination_due_date":
                nvd = record.get("next_vaccination_due_date") or record.get("next_visit_date")
                if self._is_missing(nvd):
                    missing.append("next_vaccination_due_date")
                continue

            value = record.get(field)
            if self._is_missing(value):
                missing.append(field)
        return missing

    def get_field_prompt(self, field: str) -> str:
        label = FIELD_LABELS.get(field, field.replace("_", " "))
        return f"I still need {label}. Please tell me {label}."

    def build_readback_text(self, record: dict) -> str:
        lines = ["Here is the visit information."]
        name = record.get("beneficiary_name")
        if name:
            lines.append(f"Beneficiary: {name}.")
        vtype = record.get("visit_type")
        if vtype:
            lines.append(f"Visit type: {vtype} visit.")
        vdate = record.get("visit_date")
        if vdate:
            lines.append(f"Visit date: {vdate}.")
        pm = record.get("pregnancy_month")
        if pm is not None:
            lines.append(f"Pregnancy month: {pm}.")
        wt = record.get("weight_kg")
        if wt is not None:
            lines.append(f"Weight: {wt} kilograms.")
        anc = record.get("anc_completed")
        if anc is True:
            lines.append("ANC checkup completed.")
        elif anc is False:
            lines.append("ANC checkup not yet completed.")
        ifa = record.get("ifa_given")
        if ifa is True:
            lines.append("IFA tablet given.")
        elif ifa is False:
            lines.append("IFA tablet not given.")
        vacc = record.get("vaccinations") or []
        if vacc:
            lines.append(f"Vaccinations: {', '.join(vacc)}.")
        nvd = record.get("next_visit_date")
        if nvd:
            lines.append(f"Next visit date: {nvd}.")
        lines.append("Should I save this record? Please say yes to confirm or no to make a correction.")
        return " ".join(lines)

    def validate(self, record: dict, category: Optional[str] = None) -> Tuple[bool, List[str]]:
        errors = []
        cat = category or record.get("revisit_category") or record.get("beneficiary_type")
        visit_type = record.get("visit_type", "")
        if visit_type not in VALID_VISIT_TYPES:
            errors.append(f"Invalid visit type: '{visit_type}'. Must be one of: {', '.join(sorted(VALID_VISIT_TYPES))}")
            visit_type = "household"

        for field in self.get_missing_mandatory_fields(record, category=cat):
            errors.append(f"Missing mandatory field: {field}")

        for date_field in ("visit_date", "next_visit_date", "next_vaccination_due_date"):
            val = record.get(date_field)
            if val:
                try:
                    datetime.strptime(val, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"Invalid date format for {date_field}: '{val}'. Expected YYYY-MM-DD.")

        pm = record.get("pregnancy_month")
        if pm is not None:
            try:
                pm_int = int(pm)
                if not (1 <= pm_int <= 9):
                    errors.append(f"Pregnancy month out of valid range (1-9): {pm}")
            except (ValueError, TypeError):
                errors.append(f"Pregnancy month must be an integer 1-9, got: {pm}")

        weight = record.get("weight_kg")
        if weight is not None:
            try:
                w = float(weight)
                if not (WEIGHT_MIN_KG <= w <= WEIGHT_MAX_KG):
                    errors.append(f"Weight out of realistic range ({WEIGHT_MIN_KG}–{WEIGHT_MAX_KG} kg): {weight}")
            except (ValueError, TypeError):
                errors.append(f"Weight must be a number, got: {weight}")

        if visit_type == "immunisation":
            vacc = record.get("vaccinations")
            vacc_given = record.get("vaccines_given_today")
            if not vacc and not vacc_given:
                errors.append("Immunisation visit requires at least one vaccination recorded.")

        score = float(record.get("confidence_score") or 0.0)
        if score < 0.4:
            errors.append(
                f"Low extraction confidence ({score:.0%}). "
                "Please verify or re-record the information."
            )

        if record.get("is_saved") is True:
            errors.append("This record has already been saved to the database.")

        return len(errors) == 0, errors

    def enrich_missing_fields(self, record: dict, category: Optional[str] = None) -> dict:
        cat = category or record.get("revisit_category") or record.get("beneficiary_type")
        record["missing_fields"] = self.get_missing_mandatory_fields(record, category=cat)
        return record

    def is_ready_to_save(self, record: dict, category: Optional[str] = None) -> Tuple[bool, List[str]]:
        reasons = []
        cat = category or record.get("revisit_category") or record.get("beneficiary_type")
        missing = self.get_missing_mandatory_fields(record, category=cat)
        if missing:
            reasons.append(f"Missing mandatory fields: {', '.join(missing)}")
        valid, errors = self.validate(record, category=cat)
        if not valid:
            for e in errors:
                if "Missing mandatory" not in e:
                    reasons.append(e)
        if record.get("is_saved") is True:
            reasons.append("Record already saved — will not create duplicate.")
        return len(reasons) == 0, reasons

    @staticmethod
    def _is_missing(value) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, list) and len(value) == 0:
            return True
        return False


# Singleton
validation_service = ValidationService()
