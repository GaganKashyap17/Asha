import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from rest_framework.test import APIClient
from services.mongodb_service import mongodb_service
from services.validation_service import validation_service
from services.groq_service import groq_service


@pytest.fixture
def api_client():
    return APIClient()


def test_revisit_mandatory_fields_definitions():
    """Verify all 8 mandatory fields are defined for all 3 revisit categories."""
    preg_fields = validation_service.get_mandatory_fields("pregnancy", category="pregnant_woman")
    assert preg_fields == [
        "weight_kg",
        "blood_pressure",
        "hb_level",
        "blood_sugar_level",
        "vaginal_bleeding",
        "severe_headache_blurred_vision",
        "fetal_movement",
        "ifa_calcium_consumption",
    ]

    newb_fields = validation_service.get_mandatory_fields("newborn", category="newborn")
    assert newb_fields == [
        "weight_kg",
        "temperature_celsius",
        "respiratory_rate",
        "breastfeeding_status",
        "difficulty_in_feeding",
        "difficulty_in_breathing",
        "yellowing_skin_eyes",
        "umbilical_cord_condition",
    ]

    imm_fields = validation_service.get_mandatory_fields("immunisation", category="immunization_child")
    assert imm_fields == [
        "weight_kg",
        "height_cm",
        "general_health_condition",
        "vaccines_due_today",
        "vaccines_given_today",
        "missed_vaccination_doses",
        "previous_aefi",
        "next_vaccination_due_date",
    ]


def test_single_field_extraction_regex():
    """Verify single field extraction regex correctly handles all categories."""
    # 1. Pregnant woman fields
    res_bp = groq_service.extract_single_visit_field("blood pressure is 120 over 80", "blood_pressure", "pregnant_woman")
    assert res_bp["value"] == "120/80"
    assert res_bp["blood_pressure_systolic"] == 120
    assert res_bp["blood_pressure_diastolic"] == 80

    res_hb = groq_service.extract_single_visit_field("haemoglobin level 11.4 g/dL", "hb_level", "pregnant_woman")
    assert res_hb["value"] == 11.4

    res_bs = groq_service.extract_single_visit_field("blood sugar 98 mg/dL", "blood_sugar_level", "pregnant_woman")
    assert res_bs["value"] == 98.0

    res_vb = groq_service.extract_single_visit_field("no vaginal bleeding", "vaginal_bleeding", "pregnant_woman")
    assert res_vb["value"] == "No"
    res_vb_spot = groq_service.extract_single_visit_field("mild spotting reported", "vaginal_bleeding", "pregnant_woman")
    assert res_vb_spot["value"] == "Spotting"
    res_vb_yes = groq_service.extract_single_visit_field("heavy vaginal bleeding present", "vaginal_bleeding", "pregnant_woman")
    assert res_vb_yes["value"] == "Yes"

    res_hd_no = groq_service.extract_single_visit_field("no severe headache or blurred vision", "severe_headache_blurred_vision", "pregnant_woman")
    assert res_hd_no["value"] == "No"
    res_hd_yes = groq_service.extract_single_visit_field("complaining of severe headache and blurred vision", "severe_headache_blurred_vision", "pregnant_woman")
    assert res_hd_yes["value"] == "Yes"
    res_hd_mild = groq_service.extract_single_visit_field("only mild headache", "severe_headache_blurred_vision", "pregnant_woman")
    assert res_hd_mild["value"] == "Mild Headache"

    res_fm = groq_service.extract_single_visit_field("baby movement is normal", "fetal_movement", "pregnant_woman")
    assert res_fm["value"] == "Normal"
    res_fm_red = groq_service.extract_single_visit_field("fetal movement is reduced", "fetal_movement", "pregnant_woman")
    assert res_fm_red["value"] == "Reduced"
    res_fm_abs = groq_service.extract_single_visit_field("no fetal movement absent", "fetal_movement", "pregnant_woman")
    assert res_fm_abs["value"] == "Absent"

    res_ifa_both = groq_service.extract_single_visit_field("taking both tablets regularly", "ifa_calcium_consumption", "pregnant_woman")
    assert res_ifa_both["value"] == "Both Consumed Regularly"
    res_ifa_not = groq_service.extract_single_visit_field("not consumed tablets stopped", "ifa_calcium_consumption", "pregnant_woman")
    assert res_ifa_not["value"] == "Not Consumed"
    res_ifa_miss = groq_service.extract_single_visit_field("irregular missed doses sometimes", "ifa_calcium_consumption", "pregnant_woman")
    assert res_ifa_miss["value"] == "Irregular / Missed Doses"

    # 2. Newborn fields
    res_temp = groq_service.extract_single_visit_field("temperature 36.8 celsius", "temperature_celsius", "newborn")
    assert res_temp["value"] == 36.8

    res_rr = groq_service.extract_single_visit_field("respiratory rate 48 breaths per minute", "respiratory_rate", "newborn")
    assert res_rr["value"] == 48

    res_bf = groq_service.extract_single_visit_field("exclusive breastfeeding only", "breastfeeding_status", "newborn")
    assert res_bf["value"] == "Exclusive Breastfeeding"

    # 3. Immunization fields
    res_ht = groq_service.extract_single_visit_field("height is 71.5 cm", "height_cm", "immunization_child")
    assert res_ht["value"] == 71.5

    res_date = groq_service.extract_single_visit_field("next vaccination due date 2026-12-25", "next_vaccination_due_date", "immunization_child")
    assert res_date["value"] == "2026-12-25"


def test_revisit_extract_field_api(api_client):
    """Test POST /api/visits/revisit/extract-field/ endpoint."""
    resp = api_client.post(
        "/api/visits/revisit/extract-field/",
        {
            "field": "hb_level",
            "transcript": "Haemoglobin count is 11.8",
            "category": "pregnant_woman",
        },
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["field"] == "hb_level"
    assert resp.data["value"] == 11.8


def test_newborn_revisit_full_flow(api_client):
    """Test full Newborn revisit from ID lookup to draft creation, field completion and save."""
    # Insert newborn beneficiary
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": "NEWB-987654",
        "name": "Kavya Baby",
        "beneficiary_type": "newborn",
        "is_deleted": False,
    })

    # 1. Lookup
    init_mock = {
        "beneficiary_id": "NEWB-987654",
        "spoken_name": "Kavya Baby",
    }
    with patch("services.groq_service.GroqService.extract_revisit_identity", return_value=init_mock):
        init_resp = api_client.post(
            "/api/visits/revisit/init/",
            {"transcript": "Revisit for Kavya Baby ID NEWB-987654"},
            format="json",
        )
    assert init_resp.status_code == 200
    assert init_resp.data["found"] is True

    # 2. Extract clinical data with some missing fields
    mock_clinical = {
        "visit_type": "newborn",
        "visit_date": "2026-11-21",
        "weight_kg": 3.4,
        "temperature_celsius": 36.8,
        "respiratory_rate": 45,
        "breastfeeding_status": "Exclusive Breastfeeding",
        # missing: difficulty_in_feeding, difficulty_in_breathing, yellowing_skin_eyes, umbilical_cord_condition
    }
    with patch("services.groq_service.GroqService.extract_revisit_clinical", return_value=mock_clinical):
        ext_resp = api_client.post(
            "/api/visits/revisit/extract/",
            {
                "transcript": "Weight 3.4 kg, temp 36.8, breathing 45 per min, feeding exclusively.",
                "beneficiary_id": "NEWB-987654",
                "beneficiary_type": "newborn",
            },
            format="json",
        )
    assert ext_resp.status_code == 200
    draft_id = ext_resp.data["draft_id"]
    missing = ext_resp.data["missing_fields"]
    assert "difficulty_in_feeding" in missing
    assert "yellowing_skin_eyes" in missing

    # 3. Fill missing fields via extract-field / draft-add-field
    for f, v in [
        ("difficulty_in_feeding", "No"),
        ("difficulty_in_breathing", "No"),
        ("yellowing_skin_eyes", "No"),
        ("umbilical_cord_condition", "Clean & Dry"),
    ]:
        api_client.post(f"/api/visits/draft/{draft_id}/add-field/", {"field": f, "value": v}, format="json")

    # 4. Confirm draft
    conf_resp = api_client.post(f"/api/visits/draft/{draft_id}/confirm/")
    assert conf_resp.status_code == 201

    # Verify visit saved in MongoDB
    saved = mongodb_service.find_one("visits", {"beneficiary_id": "NEWB-987654"})
    assert saved is not None
    assert saved["weight_kg"] == 3.4
    assert saved["yellowing_skin_eyes"] == "No"
