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


# Singleton
groq_service = GroqService()
