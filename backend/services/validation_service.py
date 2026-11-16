"""
Validation service — business-rule validation for visit records.
"""
import logging
from datetime import date, datetime
from typing import List, Tuple

logger = logging.getLogger(__name__)


class ValidationService:
    """Validates extracted visit data against ASHA program business rules."""

    REQUIRED_FIELDS_BY_VISIT_TYPE = {
        "pregnancy": ["beneficiary_name", "pregnancy_month", "weight_kg"],
        "newborn": ["beneficiary_name", "weight_kg"],
        "postnatal": ["beneficiary_name", "weight_kg"],
        "immunisation": ["beneficiary_name", "vaccinations"],
        "household": ["beneficiary_name"],
    }

    def validate(self, record: dict) -> Tuple[bool, List[str]]:
        """
        Validate a visit record dict.

        Returns:
            (is_valid, list_of_validation_errors)
        """
        errors = []
        visit_type = record.get("visit_type", "household")

        # Required fields check
        required = self.REQUIRED_FIELDS_BY_VISIT_TYPE.get(visit_type, [])
        for field in required:
            value = record.get(field)
            if value is None or value == [] or value == "":
                errors.append(f"Missing required field: {field} for visit type {visit_type}")

        # Date format check
        for date_field in ["visit_date", "next_visit_date"]:
            val = record.get(date_field)
            if val:
                try:
                    datetime.strptime(val, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"Invalid date format for {date_field}: {val}")

        # Pregnancy month range
        preg_month = record.get("pregnancy_month")
        if preg_month is not None:
            if not (1 <= int(preg_month) <= 9):
                errors.append(f"Pregnancy month out of range (1-9): {preg_month}")

        # Weight sanity
        weight = record.get("weight_kg")
        if weight is not None:
            if not (0.5 <= float(weight) <= 200):
                errors.append(f"Weight out of realistic range: {weight} kg")

        # Confidence score
        score = record.get("confidence_score", 0)
        if score < 0.4:
            errors.append(f"Low confidence score ({score}): review extraction carefully")

        return len(errors) == 0, errors

    def enrich_missing_fields(self, record: dict) -> dict:
        """Add missing_fields list based on what's None."""
        visit_type = record.get("visit_type", "household")
        required = self.REQUIRED_FIELDS_BY_VISIT_TYPE.get(visit_type, [])
        missing = [f for f in required if record.get(f) is None or record.get(f) == []]
        record["missing_fields"] = missing
        return record


# Singleton
validation_service = ValidationService()
