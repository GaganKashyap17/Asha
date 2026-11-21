"""
Tests for Gnani API Platform Beneficiary Registration Bar.
Verifies Prisma v3.0 STT, Timbre v3.0 TTS, Groq extraction integration,
mandatory field validation, duplicate detection, and unique ID generation.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from rest_framework import status
from services.gnani_service import gnani_service
from apps.voice_agent.gnani_views import gnani_status, gnani_tts, gnani_translate
from apps.beneficiaries.views import beneficiary_register_voice, beneficiary_list_create
from services.groq_service import groq_service


@pytest.fixture
def rf():
    return RequestFactory()


def test_gnani_service_configuration():
    """Verify GnaniService loads correct models and API status."""
    assert gnani_service.is_configured is True
    st = gnani_service.status()
    assert st["configured"] is True
    assert st["stt_model"] == "prisma-v3.0"
    assert st["tts_model"] == "timbre-v3.0"
    assert len(st["supported_languages"]) >= 4


def test_gnani_ws_headers_generation():
    """Verify WebSocket upgrade headers conform to Gnani Prisma v3.0 specifications."""
    headers = gnani_service.get_ws_headers("ta")
    assert "x-api-key-id" in headers
    assert headers["model"] == "prisma-v3.0"
    assert headers["language_code"] == "ta-IN"
    assert headers["partials_enabled"] == "true"
    assert headers["format"] == "verbatim"


def test_gnani_service_key_redaction():
    """Verify GnaniService never leaks the API key in logs or error messages."""
    msg = f"Failed to connect with key {gnani_service._api_key} on host"
    redacted = gnani_service._redact(msg)
    assert gnani_service._api_key not in redacted
    assert "[REDACTED_GNANI_KEY]" in redacted


def test_gnani_status_endpoint(rf):
    """GET /api/voice/gnani/status/ returns 200 and model details."""
    request = rf.get("/api/voice/gnani/status/")
    response = gnani_status(request)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["stt_model"] == "prisma-v3.0"
    assert response.data["tts_model"] == "timbre-v3.0"


def test_gnani_tts_endpoint_validation(rf):
    """POST /api/voice/gnani/tts/ validates input and rejects empty text."""
    request = rf.post("/api/voice/gnani/tts/", {}, content_type="application/json")
    response = gnani_tts(request)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "error" in response.data


def test_gnani_tts_synthesis_mock(rf):
    """POST /api/voice/gnani/tts/ returns audio/wav on successful synthesis."""
    fake_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00data\x00\x00\x00\x00"
    with patch.object(gnani_service, "synthesize_speech", return_value={"audio_bytes": fake_wav, "format": "wav", "error": None}):
        request = rf.post(
            "/api/voice/gnani/tts/",
            {"text": "தயவுசெய்து விடுபட்ட தகவல்களை வழங்கவும்", "language": "ta"},
            content_type="application/json"
        )
        response = gnani_tts(request)
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "audio/wav"
        assert response.content == fake_wav


def test_gnani_translate_endpoint(rf):
    """POST /api/voice/gnani/translate/ translates vernacular speech to English."""
    with patch.object(groq_service, "translate_to_english", return_value="Her name is Meena and she is 24 years old."):
        request = rf.post(
            "/api/voice/gnani/translate/",
            {"text": "அவள் பெயர் மீனா வயது 24", "source_language": "ta"},
            content_type="application/json"
        )
        response = gnani_translate(request)
        assert response.status_code == status.HTTP_200_OK
        assert "Meena" in response.data["translated_text"]


def test_gnani_bar_end_to_end_pipeline(rf):
    """
    End-to-end test simulating Gnani Voice Registration:
    Gnani Prisma transcript -> Groq extraction -> Category validation -> Unique ID generation & MongoDB save.
    """
    gnani_transcript = (
        "Register pregnant woman Lakshmi, 26 years old, phone 9876501234, "
        "address Gandhi Street Coimbatore, pregnancy registered, LMP 2026-06-15, "
        "EDD 2027-03-22, gestational age 18 weeks, gravida 2, previous live births 1, no complications."
    )

    mock_extracted = {
        "name": "Lakshmi",
        "age": 26,
        "phone": "9876501234",
        "address": "Gandhi Street Coimbatore",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-06-15",
        "edd": "2027-03-22",
        "gestational_age_weeks": 18,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "none",
    }

    with patch.object(groq_service, "extract_beneficiary_registration", return_value=mock_extracted):
        reg_req = rf.post(
            "/api/beneficiaries/register-voice/",
            {"transcript": gnani_transcript, "beneficiary_type": "pregnant_woman", "language": "en"},
            content_type="application/json"
        )
        reg_resp = beneficiary_register_voice(reg_req)
        assert reg_resp.status_code == status.HTTP_200_OK
        data = reg_resp.data

        # Check extracted fields
        assert data["extracted"]["name"] == "Lakshmi"
        assert len(data["missing_mandatory"]) == 0

        # Save via existing beneficiary service & MongoDB
        save_payload = {
            "beneficiary_type": "pregnant_woman",
            **data["extracted"]
        }

        save_req = rf.post(
            "/api/beneficiaries/",
            save_payload,
            content_type="application/json"
        )
        save_resp = beneficiary_list_create(save_req)
        assert save_resp.status_code == status.HTTP_201_CREATED
        saved_record = save_resp.data
        assert "beneficiary_id" in saved_record
        assert saved_record["beneficiary_id"].startswith("PREG-")
        assert saved_record["name"] == "Lakshmi"


def test_noisy_speech_number_extraction(rf):
    """Verify that spoken phrases like 'Bottle Pregnancy is one.' normalize to int 1."""
    from services.beneficiary_validation_service import extract_int_value, extract_float_value
    from apps.beneficiaries.views import beneficiary_extract_field

    assert extract_int_value("Bottle Pregnancy is one.") == 1
    assert extract_int_value("first pregnancy") == 1
    assert extract_int_value("None") == 0
    assert extract_int_value("two") == 2
    assert extract_float_value("2.8 kg") == 2.8

    # Test beneficiary_extract_field API with noisy string for gravida
    req = rf.post(
        "/api/beneficiaries/extract-field/",
        {"field": "gravida", "transcript": "Bottle Pregnancy is one.", "category": "pregnant_woman"},
        content_type="application/json"
    )
    resp = beneficiary_extract_field(req)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["value"] == 1

    # Test non-numeric speech does not set arbitrary text on numeric field
    req2 = rf.post(
        "/api/beneficiaries/extract-field/",
        {"field": "gravida", "transcript": "some random sound", "category": "pregnant_woman"},
        content_type="application/json"
    )
    resp2 = beneficiary_extract_field(req2)
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.data["value"] is None

