"""
Comprehensive test suite for Category-Based Beneficiary Registration & Unique ID Generation.

Covers:
- Category 1: Pregnant Woman
- Category 2: Newborn
- Category 3: Immunization / Child
- Category 4: Other Beneficiary
- Mandatory Validation & Inconsistency Rules
- Beneficiary ID Generation rules (only generated on confirm, never in preview)
- Concurrency & Uniqueness
"""
import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from services.mongodb_service import mongodb_service
from services.id_generation_service import generate_category_beneficiary_id
from services.beneficiary_validation_service import validate_beneficiary_data


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
# 1. CATEGORY 1 – PREGNANT WOMAN
# ─────────────────────────────────────────────────────────────────────────────

def test_pregnant_woman_complete_registration(api_client):
    """Complete valid pregnant woman registration generates PREG-xxxxxx ID."""
    payload = {
        "beneficiary_type": "pregnant_woman",
        "name": "Lakshmi",
        "age": 25,
        "address": "Coimbatore, H102",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-08-10",
        "edd": "2027-05-17",
        "gestational_age_weeks": 14,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "None reported",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 201
    data = resp.data
    assert data["beneficiary_id"].startswith("PREG-")
    assert data["pregnancy_details"]["lmp"] == "2026-08-10"
    assert data["pregnancy_details"]["previous_live_births"] == 1
    assert data["pregnancy_details"]["previous_complications"] == "None reported"


def test_pregnant_woman_missing_lmp_rejected(api_client):
    """Missing LMP fails validation and prevents database save and ID generation."""
    payload = {
        "beneficiary_type": "pregnant_woman",
        "name": "Lakshmi",
        "age": 25,
        "address": "Coimbatore",
        "pregnancy_registration_status": "registered",
        # "lmp": missing
        "edd": "2027-05-17",
        "gestational_age_weeks": 14,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "None reported",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert "lmp" in resp.data["missing_mandatory"]
    assert len(mongodb_service.find_all("beneficiaries")) == 0


def test_pregnant_woman_invalid_edd_format(api_client):
    """Invalid EDD format is rejected."""
    payload = {
        "beneficiary_type": "pregnant_woman",
        "name": "Lakshmi",
        "age": 25,
        "address": "Coimbatore",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-08-10",
        "edd": "invalid-date",
        "gestational_age_weeks": 14,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "None reported",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert any("EDD date" in err for err in resp.data["validation_errors"])


def test_pregnant_woman_inconsistent_lmp_edd(api_client):
    """EDD on or before LMP is flagged as inconsistent and rejected."""
    payload = {
        "beneficiary_type": "pregnant_woman",
        "name": "Lakshmi",
        "age": 25,
        "address": "Coimbatore",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-08-10",
        "edd": "2026-08-01",  # Before LMP!
        "gestational_age_weeks": 14,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "None reported",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert any("before LMP" in err for err in resp.data["validation_errors"])


def test_pregnant_woman_live_births_exceed_gravida(api_client):
    """Live births > gravida is rejected."""
    payload = {
        "beneficiary_type": "pregnant_woman",
        "name": "Lakshmi",
        "age": 25,
        "address": "Coimbatore",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-08-10",
        "edd": "2027-05-17",
        "gestational_age_weeks": 14,
        "gravida": 1,
        "previous_live_births": 3,  # Exceeds gravida!
        "previous_complications": "None reported",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert any("cannot exceed" in err for err in resp.data["validation_errors"])


# ─────────────────────────────────────────────────────────────────────────────
# 2. CATEGORY 2 – NEWBORN
# ─────────────────────────────────────────────────────────────────────────────

def test_newborn_complete_registration_with_mother_name(api_client):
    """Complete newborn registration with mother's name."""
    payload = {
        "beneficiary_type": "newborn",
        "name": "Arjun",
        "dob": "2026-11-15",
        "gender": "male",
        "mother_name": "Lakshmi",
        "place_of_delivery": "Government Hospital, Coimbatore",
        "birth_weight_kg": 2.8,
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 201
    assert resp.data["beneficiary_id"].startswith("NEWB-")
    assert resp.data["newborn_details"]["birth_weight_kg"] == 2.8


def test_newborn_complete_with_valid_mother_id(api_client):
    """Newborn linked to registered mother ID succeeds."""
    # Seed mother
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "PREG-000001",
        "name": "Lakshmi",
        "beneficiary_type": "pregnant_woman",
        "is_deleted": False,
    })

    payload = {
        "beneficiary_type": "newborn",
        "name": "Arjun",
        "dob": "2026-11-15",
        "gender": "male",
        "mother_beneficiary_id": "PREG-000001",
        "place_of_delivery": "Government Hospital",
        "birth_weight_kg": 3.1,
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 201
    assert resp.data["newborn_details"]["mother_beneficiary_id"] == "PREG-000001"
    assert resp.data["newborn_details"]["mother_name"] == "Lakshmi"


def test_newborn_invalid_mother_id_rejected(api_client):
    """If supplied mother's Beneficiary ID does not exist, registration is blocked."""
    payload = {
        "beneficiary_type": "newborn",
        "name": "Arjun",
        "dob": "2026-11-15",
        "gender": "male",
        "mother_beneficiary_id": "PREG-999999",  # Non-existent
        "place_of_delivery": "Government Hospital",
        "birth_weight_kg": 3.1,
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert any("does not exist" in err for err in resp.data["validation_errors"])


def test_newborn_missing_birth_weight_rejected(api_client):
    """Missing birth weight is rejected."""
    payload = {
        "beneficiary_type": "newborn",
        "name": "Arjun",
        "dob": "2026-11-15",
        "gender": "male",
        "mother_name": "Lakshmi",
        "place_of_delivery": "Government Hospital",
        # "birth_weight_kg": missing
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert "birth_weight_kg" in resp.data["missing_mandatory"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. CATEGORY 3 – IMMUNIZATION / CHILD
# ─────────────────────────────────────────────────────────────────────────────

def test_immunization_child_complete_registration(api_client):
    """Complete immunization registration generates IMM-xxxxxx ID."""
    payload = {
        "beneficiary_type": "immunization_child",
        "name": "Kavin",
        "dob": "2026-01-10",
        "gender": "male",
        "mother_name": "Meena",
        "immunization_card_status": "yes",
        "vaccination_status": "BCG received, OPV pending",
        "vaccinations_received": ["BCG", "HepB"],
        "vaccinations_pending": ["OPV-1", "Pentavalent-1"],
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 201
    assert resp.data["beneficiary_id"].startswith("IMM-")
    assert resp.data["immunization_details"]["immunization_card_status"] == "yes"
    assert "BCG" in resp.data["immunization_details"]["vaccinations_received"]


def test_immunization_child_missing_card_status(api_client):
    """Missing immunization card status fails validation."""
    payload = {
        "beneficiary_type": "immunization_child",
        "name": "Kavin",
        "dob": "2026-01-10",
        "gender": "male",
        "mother_name": "Meena",
        # "immunization_card_status": missing
        "vaccination_status": "Received BCG",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert "immunization_card_status" in resp.data["missing_mandatory"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. CATEGORY 4 – OTHER BENEFICIARY
# ─────────────────────────────────────────────────────────────────────────────

def test_other_beneficiary_complete_registration(api_client):
    """Complete registration for Other Beneficiary generates BEN-xxxxxx ID."""
    payload = {
        "beneficiary_type": "other",
        "name": "Ravi Kumar",
        "phone": "9876543210",
        "beneficiary_category": "Elderly Care",
        "address": "Coimbatore, Gandhi Road",
        "emergency_contact": "9876501234",
        "blood_group": "O+",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 201
    assert resp.data["beneficiary_id"].startswith("BEN-")
    assert resp.data["other_beneficiary_details"]["blood_group"] == "O+"


def test_other_beneficiary_invalid_phone_rejected(api_client):
    """Invalid Indian phone number fails validation."""
    payload = {
        "beneficiary_type": "other",
        "name": "Ravi Kumar",
        "phone": "12345",  # Invalid!
        "beneficiary_category": "Elderly Care",
        "address": "Coimbatore",
        "emergency_contact": "9876501234",
        "blood_group": "O+",
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert any("Phone number" in err for err in resp.data["validation_errors"])


def test_other_beneficiary_invalid_blood_group(api_client):
    """Unsupported blood group fails validation."""
    payload = {
        "beneficiary_type": "other",
        "name": "Ravi Kumar",
        "phone": "9876543210",
        "beneficiary_category": "Elderly Care",
        "address": "Coimbatore",
        "emergency_contact": "9876501234",
        "blood_group": "XYZ",  # Unsupported
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 422
    assert any("Blood group" in err for err in resp.data["validation_errors"])


# ─────────────────────────────────────────────────────────────────────────────
# 5. VOICE PREVIEW DOES NOT GENERATE ID
# ─────────────────────────────────────────────────────────────────────────────

def test_voice_register_preview_does_not_generate_id(api_client):
    """
    Critical Rule: Beneficiary ID is NEVER generated during preview/voice extraction.
    Only generated after validation and confirmation.
    """
    mock_extracted = {
        "name": "Lakshmi",
        "age": 25,
        "address": "Coimbatore",
        "pregnancy_registration_status": "registered",
        "lmp": "2026-08-10",
        "edd": "2027-05-17",
        "gestational_age_weeks": 14,
        "gravida": 2,
        "previous_live_births": 1,
        "previous_complications": "None reported",
    }
    with patch("services.groq_service.GroqService.extract_beneficiary_registration", return_value=mock_extracted):
        resp = api_client.post(
            "/api/beneficiaries/register-voice/",
            {
                "transcript": "Her name is Lakshmi 25 years old 14 weeks pregnant",
                "beneficiary_type": "pregnant_woman",
                "language": "en"
            },
            format="json",
        )
    assert resp.status_code == 200
    assert resp.data["beneficiary_id"] is None
    # Ensure nothing was saved in the database
    assert len(mongodb_service.find_all("beneficiaries")) == 0


def test_newborn_flexible_mother_id_matching(api_client):
    """Zero-padded or unpadded mother ID (e.g. PREG-00004 vs PREG-000004) successfully matches."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "PREG-000004",
        "name": "Priya",
        "beneficiary_type": "pregnant_woman",
        "is_deleted": False,
    })

    payload = {
        "beneficiary_type": "newborn",
        "name": "Baby of Priya",
        "dob": "2026-11-20",
        "gender": "female",
        "mother_beneficiary_id": "PREG-00004",  # 4 zeroes instead of 5
        "place_of_delivery": "Government Hospital",
        "birth_weight_kg": 2.9,
    }
    resp = api_client.post("/api/beneficiaries/", payload, format="json")
    assert resp.status_code == 201
    assert resp.data["newborn_details"]["mother_beneficiary_id"] == "PREG-000004"
    assert resp.data["newborn_details"]["mother_name"] == "Priya"


def test_beneficiary_lookup_flexible_id(api_client):
    """Lookup /lookup/PREG-00004/ finds PREG-000004 successfully."""
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "PREG-000004",
        "name": "Priya",
        "beneficiary_type": "pregnant_woman",
        "is_deleted": False,
    })

    resp = api_client.get("/api/beneficiaries/lookup/PREG-00004/")
    assert resp.status_code == 200
    assert resp.data["found"] is True
    assert resp.data["beneficiary"]["beneficiary_id"] == "PREG-000004"
