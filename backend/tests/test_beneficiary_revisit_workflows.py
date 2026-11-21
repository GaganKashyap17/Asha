"""
Comprehensive tests for Beneficiary Bar (New Registration) & Revisit Bar (Existing Beneficiary Revisit).
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from services.mongodb_service import mongodb_service


@pytest.fixture(autouse=True)
def clean_db():
    if mongodb_service._memory_store is not None:
        mongodb_service._memory_store = {col: [] for col in mongodb_service.COLLECTIONS}
    else:
        mongodb_service._use_memory_fallback()
    mongodb_service.connected = False
    yield
    if mongodb_service._memory_store is not None:
        mongodb_service._memory_store = {col: [] for col in mongodb_service.COLLECTIONS}


@pytest.fixture
def api_client():
    return APIClient()


# ─────────────────────────────────────────────────────────────────────────────
# Beneficiary Bar: New Registration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_beneficiary_register_voice_pregnant_woman(api_client):
    """Test voice extraction for new pregnant woman registration."""
    mock_extracted = {
        "name": "Lakshmi",
        "age": 25,
        "address": "Tambaram",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-08-10",
        "edd": "2027-05-17",
        "gestational_age_weeks": 14,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "None reported",
        "phone": "9876543210",
        "village": "Tambaram",
    }
    with patch("services.groq_service.GroqService.extract_beneficiary_registration", return_value=mock_extracted):
        resp = api_client.post(
            "/api/beneficiaries/register-voice/",
            {"transcript": "Her name is Lakshmi, 25 years old, 7 months pregnant.", "beneficiary_type": "pregnant_woman", "language": "en"},
            format="json",
        )
    assert resp.status_code == 200
    data = resp.data
    assert data["is_ready"] is True
    assert data["extracted"]["name"] == "Lakshmi"
    assert data["beneficiary_id"] is None
    assert data["duplicate_warning"] is None


def test_beneficiary_register_voice_missing_mandatory(api_client):
    """Missing mandatory field (lmp) marks record as not ready."""
    mock_extracted = {
        "name": "Meena",
        "age": 22,
        "pregnancy_status": "pregnant",
        "lmp": None,
    }
    with patch("services.groq_service.GroqService.extract_beneficiary_registration", return_value=mock_extracted):
        resp = api_client.post(
            "/api/beneficiaries/register-voice/",
            {"transcript": "Meena is 22 years old and pregnant.", "beneficiary_type": "pregnant_woman"},
            format="json",
        )
    assert resp.status_code == 200
    assert resp.data["is_ready"] is False
    assert "lmp" in resp.data["missing_mandatory"]


def test_beneficiary_register_voice_duplicate_warning(api_client):
    """Detects existing beneficiary with same name and flags duplicate warning."""
    # Seed existing beneficiary
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "BEN001",
        "name": "Lakshmi Sundaram",
        "village": "Tambaram",
        "phone": "9876543210",
        "is_deleted": False,
    })

    mock_extracted = {
        "name": "Lakshmi Sundaram",
        "pregnancy_status": "pregnant",
        "pregnancy_month": 4,
        "phone": "9876543210",
    }
    with patch("services.groq_service.GroqService.extract_beneficiary_registration", return_value=mock_extracted):
        resp = api_client.post(
            "/api/beneficiaries/register-voice/",
            {"transcript": "Lakshmi Sundaram 4 months pregnant.", "beneficiary_type": "pregnant_woman"},
            format="json",
        )
    assert resp.status_code == 200
    assert resp.data["duplicate_warning"] is not None
    assert resp.data["duplicate_warning"]["existing_id"] == "BEN001"
    assert resp.data["duplicate_warning"]["phone_match"] is True


def test_beneficiary_check_duplicate_endpoint(api_client):
    """Test explicit check-duplicate endpoint."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "BEN005",
        "name": "Priya",
        "phone": "9123456789",
        "is_deleted": False,
    })

    resp = api_client.post("/api/beneficiaries/check-duplicate/", {"name": "Priya"}, format="json")
    assert resp.status_code == 200
    assert resp.data["count"] == 1
    assert resp.data["duplicates"][0]["beneficiary_id"] == "BEN005"


def test_beneficiary_lookup_found_and_not_found(api_client):
    """Test lookup endpoint returns 200 when found, 404 when not found."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "BEN010",
        "name": "Ananya",
        "is_deleted": False,
    })

    # Found
    resp1 = api_client.get("/api/beneficiaries/lookup/BEN010/")
    assert resp1.status_code == 200
    assert resp1.data["found"] is True
    assert resp1.data["beneficiary"]["name"] == "Ananya"

    # Not found
    resp2 = api_client.get("/api/beneficiaries/lookup/BEN999/")
    assert resp2.status_code == 404
    assert resp2.data["found"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Revisit Bar: Verification & Clinical Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_revisit_init_exact_match(api_client):
    """Revisit step 1: Identity extracted, ID found, name matches."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "BEN001",
        "name": "Lakshmi",
        "pregnancy_status": "pregnant",
        "is_deleted": False,
    })

    with patch("services.groq_service.GroqService.extract_revisit_identity", return_value={"beneficiary_id": "BEN001", "spoken_name": "Lakshmi"}):
        resp = api_client.post(
            "/api/visits/revisit/init/",
            {"transcript": "Revisit for Lakshmi BEN zero zero one"},
            format="json",
        )
    assert resp.status_code == 200
    data = resp.data
    assert data["found"] is True
    assert data["name_match"] is True
    assert data["name_match_quality"] == "exact"
    assert data["existing_beneficiary"]["name"] == "Lakshmi"
    assert data["warning_message"] is None


def test_revisit_init_name_mismatch(api_client):
    """Revisit step 1: ID found, but name spoken does not match record."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "BEN002",
        "name": "Meena",
        "is_deleted": False,
    })

    with patch("services.groq_service.GroqService.extract_revisit_identity", return_value={"beneficiary_id": "BEN002", "spoken_name": "Kavitha"}):
        resp = api_client.post(
            "/api/visits/revisit/init/",
            {"transcript": "Revisit for Kavitha BEN002"},
            format="json",
        )
    assert resp.status_code == 200
    assert resp.data["found"] is True
    assert resp.data["name_match"] is False
    assert "mismatch" in resp.data["warning_message"].lower()


def test_revisit_init_id_not_found(api_client):
    """Revisit step 1: ID not found in database."""
    with patch("services.groq_service.GroqService.extract_revisit_identity", return_value={"beneficiary_id": "BEN999", "spoken_name": "Lakshmi"}):
        resp = api_client.post(
            "/api/visits/revisit/init/",
            {"transcript": "Revisit for Lakshmi BEN 999"},
            format="json",
        )
    assert resp.status_code == 200
    assert resp.data["found"] is False
    assert "No active beneficiary found" in resp.data["warning_message"]


def test_revisit_extract_clinical_flow(api_client):
    """Revisit step 2: Identity confirmed, clinical data extracted into draft."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "BEN001",
        "name": "Lakshmi",
        "pregnancy_status": "pregnant",
        "is_deleted": False,
    })

    mock_clinical = {
        "visit_type": "pregnancy",
        "visit_date": "2026-11-20",
        "pregnancy_month": 8,
        "weight_kg": 58.5,
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 80,
        "hb_level": 11.5,
        "blood_sugar_level": 95,
        "vaginal_bleeding": "No",
        "severe_headache_blurred_vision": "No",
        "fetal_movement": "Normal",
        "ifa_calcium_consumption": "Both Consumed Regularly",
        "ifa_given": True,
        "next_visit_date": "2026-12-05",
        "danger_signs": [],
    }

    with patch("services.groq_service.GroqService.extract_revisit_clinical", return_value=mock_clinical):
        resp = api_client.post(
            "/api/visits/revisit/extract/",
            {
                "transcript": "Lakshmi is 8 months pregnant, weight 58.5 kg, BP 120/80, IFA given, next visit December 5.",
                "beneficiary_id": "BEN001",
                "beneficiary_type": "pregnant_woman",
            },
            format="json",
        )
    assert resp.status_code == 200
    data = resp.data
    assert "draft_id" in data
    assert data["is_complete"] is True
    assert data["record"]["beneficiary_id"] == "BEN001"
    assert data["record"]["beneficiary_name"] == "Lakshmi"
    assert data["record"]["weight_kg"] == 58.5

    # Verify visit is NOT yet saved to MongoDB visits collection
    visits_in_db = mongodb_service.find_all("visits", {"beneficiary_id": "BEN001"})
    assert len(visits_in_db) == 0

    # Step 3: Now confirm draft to save to MongoDB
    draft_id = data["draft_id"]
    confirm_resp = api_client.post(f"/api/visits/draft/{draft_id}/confirm/")
    assert confirm_resp.status_code == 201

    # Verify visit is now saved
    saved_visits = mongodb_service.find_all("visits", {"beneficiary_id": "BEN001"})
    assert len(saved_visits) == 1
    assert saved_visits[0]["weight_kg"] == 58.5

    # Verify beneficiary was updated, NOT duplicated
    all_beneficiaries = mongodb_service.find_all("beneficiaries", {"beneficiary_id": "BEN001"})
    assert len(all_beneficiaries) == 1
    assert all_beneficiaries[0]["last_visit_date"] == "2026-11-20"
    assert all_beneficiaries[0]["next_visit_date"] == "2026-12-05"
