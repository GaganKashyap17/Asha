"""
Extraction service — Pydantic schema + orchestration for visit data extraction.
"""
import json
import logging
from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class VisitRecord(BaseModel):
    """Pydantic schema for extracted visit data."""
    beneficiary_name: Optional[str] = None
    beneficiary_id: Optional[str] = None
    visit_type: str = "household"
    visit_date: Optional[str] = None  # YYYY-MM-DD
    pregnancy_month: Optional[int] = None
    weight_kg: Optional[float] = None
    anc_completed: Optional[bool] = None
    ifa_given: Optional[bool] = None
    vaccinations: List[str] = Field(default_factory=list)
    danger_signs: List[str] = Field(default_factory=list)
    danger_flag: bool = False
    next_visit_date: Optional[str] = None  # YYYY-MM-DD
    pending_actions: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    uncertain_fields: List[str] = Field(default_factory=list)
    confirmation_status: str = "pending"
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator('visit_date', 'next_visit_date', mode='before')
    @classmethod
    def validate_date_format(cls, v):
        if v is None:
            return None
        if isinstance(v, (date, datetime)):
            return v.strftime('%Y-%m-%d')
        if isinstance(v, str):
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                logger.warning(f"Invalid date format: {v}, setting to null")
                return None
        return None

    @field_validator('visit_type', mode='before')
    @classmethod
    def validate_visit_type(cls, v):
        allowed = {'pregnancy', 'newborn', 'postnatal', 'immunisation', 'household'}
        if v not in allowed:
            return 'household'
        return v

    @field_validator('weight_kg', mode='before')
    @classmethod
    def validate_weight(cls, v):
        if v is None:
            return None
        try:
            w = float(v)
            # Sanity check: 0.5kg to 200kg
            if 0.5 <= w <= 200:
                return round(w, 2)
            logger.warning(f"Weight out of range: {w}")
            return None
        except (ValueError, TypeError):
            return None

    @field_validator('pregnancy_month', mode='before')
    @classmethod
    def validate_pregnancy_month(cls, v):
        if v is None:
            return None
        try:
            m = int(v)
            if 1 <= m <= 9:
                return m
            return None
        except (ValueError, TypeError):
            return None


class ExtractionService:
    """Orchestrates transcript -> VisitRecord pipeline."""

    def extract_from_transcript(self, transcript: str, visit_type: str) -> dict:
        """
        Extract visit data via Groq LLM then validate with Pydantic.

        Returns dict (serialized VisitRecord) or error dict.
        """
        from services.groq_service import groq_service
        from services.danger_detection_service import detect_danger_signs

        try:
            raw = groq_service.extract_visit_data(transcript, visit_type)
        except Exception as e:
            logger.error(f"LLM extraction failed: {type(e).__name__}")
            # Return minimal structure on failure
            return {
                "error": f"Extraction failed: {type(e).__name__}",
                "confirmation_status": "error",
                "transcript": transcript,
            }

        try:
            record = VisitRecord(**raw)
        except Exception as e:
            logger.warning(f"Pydantic validation error: {e}")
            # Attempt best-effort
            record = VisitRecord(
                visit_type=raw.get('visit_type', visit_type),
                confirmation_status="pending",
                confidence_score=raw.get('confidence_score', 0.0),
            )

        # Run deterministic danger detection (overrides LLM)
        danger_results = detect_danger_signs(transcript, visit_type)
        confirmed_dangers = [r for r in danger_results if r.detected]

        if confirmed_dangers:
            record.danger_flag = True
            record.danger_signs = list({r.name for r in confirmed_dangers})
        
        result = record.model_dump()
        result['danger_detection_results'] = [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "detected": r.detected,
                "severity": r.severity,
                "is_negated": r.is_negated,
                "is_historical": r.is_historical,
                "referral_message_en": r.referral_message_en if r.detected else None,
                "referral_message_ta": r.referral_message_ta if r.detected else None,
                "source": r.source,
                "disclaimer": r.disclaimer,
            }
            for r in danger_results
        ]
        return result


# Singleton
extraction_service = ExtractionService()
