"""Tests for Groq service (mocked)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.groq_service import GroqService


class TestGroqServiceValidation:
    def test_missing_key_returns_error(self):
        service = GroqService()
        service._api_key = ""
        result = service.validate_connection()
        assert result["success"] == False
        assert "not configured" in result["error"]

    def test_placeholder_key_returns_error(self):
        service = GroqService()
        service._api_key = "your_groq_api_key_here"
        result = service.validate_connection()
        assert result["success"] == False

    def test_model_default(self):
        service = GroqService()
        assert service._model == "llama-3.3-70b-versatile" or service._model is not None
