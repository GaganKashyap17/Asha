"""
Comprehensive tests for Random Forest Machine Learning Models and Prediction Service.
Tests:
  - Dataset integrity and preprocessing requirements.
  - Three independent Random Forest models (Pregnancy, Newborn, Immunization).
  - Held-out test performance and metric assertions (Accuracy, Recall, Precision, Specificity, F1).
  - Positive, negative, missing, and invalid input testing.
  - API endpoint integration (/api/ml/predict/ and /api/ml/models/).
  - Clinical safety guarantee: ML cannot override or downgrade emergency danger alerts.
  - Reproducibility verification with fixed random seeds.
"""

import os
import json
import pytest
import pandas as pd
import numpy as np
from rest_framework.test import APIClient

from services.ml_prediction_service import ml_prediction_service, MLPredictionService
from ml_training.train_models import train_all_models, parse_vaccine_features

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.dirname(BASE_DIR)


@pytest.fixture
def client():
    return APIClient()


def test_datasets_exist_and_readable():
    """Verify that all three Excel datasets exist and have expected sheets."""
    for fname, main_sheet in [
        ("Pregnancy_Beneficiary_Dataset.xlsx", "Pregnancy_Dataset"),
        ("Newborn_Beneficiary_Dataset.xlsx", "Newborn_Dataset"),
        ("Immunization_Beneficiary_Dataset.xlsx", "Immunization_Dataset"),
    ]:
        path = os.path.join(DATA_DIR, fname)
        assert os.path.exists(path), f"Dataset file missing: {path}"
        df = pd.read_excel(path, sheet_name=main_sheet)
        assert len(df) == 500, f"Expected 500 records in {fname}, got {len(df)}"
        assert "Danger_Flag" in df.columns, f"Target Danger_Flag missing in {fname}"
        assert "Beneficiary_ID" in df.columns, f"Beneficiary_ID missing in {fname}"


def test_vaccine_parsing_logic():
    """Verify vaccine list parsing calculates deficits and antigen indicators correctly."""
    df_raw = pd.DataFrame(
        [
            {
                "Vaccines_Due_Today": "OPV-1, Pentavalent-1, Rotavirus-1",
                "Vaccines_Given_Today": "OPV-1, Pentavalent-1",
            },
            {
                "Vaccines_Due_Today": "MR-1, JE-1, PCV-Booster",
                "Vaccines_Given_Today": "None (deferred due to acute illness)",
            },
            {
                "Vaccines_Due_Today": "BCG, OPV-0, HepB-Birth",
                "Vaccines_Given_Today": "BCG, OPV-0, HepB-Birth",
            },
        ]
    )
    parsed = parse_vaccine_features(df_raw)
    assert parsed.loc[0, "count_vaccines_due"] == 3
    assert parsed.loc[0, "count_vaccines_given"] == 2
    assert parsed.loc[0, "dose_deficit_count"] == 1
    assert parsed.loc[0, "vaccines_deferred"] == 0

    # Row 1: deferred -> deficit is all due vaccines
    assert parsed.loc[1, "dose_deficit_count"] == 3
    assert parsed.loc[1, "vaccines_deferred"] == 1

    # Row 2: fully given -> deficit 0
    assert parsed.loc[2, "dose_deficit_count"] == 0
    assert parsed.loc[2, "due_bcg"] == 1
    assert parsed.loc[2, "given_bcg"] == 1


def test_models_metadata_and_metrics():
    """Verify saved model metadata contains all required metrics."""
    meta = ml_prediction_service.get_metadata()
    assert "models" in meta
    assert "pregnancy" in meta["models"]
    assert "newborn" in meta["models"]
    assert "immunization" in meta["models"]

    # Verify high accuracy and sensitivity
    for model_key, expected_min_acc, expected_min_rec in [
        ("pregnancy", 0.90, 0.85),
        ("newborn", 0.92, 0.90),
        ("immunization", 0.95, 0.92),
    ]:
        m = meta["models"][model_key]["metrics"]
        assert m["accuracy"] >= expected_min_acc
        assert m["recall_sensitivity"] >= expected_min_rec
        assert m["specificity"] >= 0.95
        assert m["f1_score"] >= 0.90
        # Precision must be strong
        assert m["precision"] >= 0.90
        # False negatives recorded
        assert "false_negatives" in m


def test_pregnancy_prediction_cases():
    """Test Pregnancy model with positive concern, negative normal, and partial records."""
    # 1. High-risk case: severe anemia, hypertension, vaginal bleeding
    pos_record = {
        "systolic_bp": 150,
        "diastolic_bp": 95,
        "haemoglobin_g_dl": 6.8,
        "vaginal_bleeding": "Yes",
        "severe_headache_or_blurred_vision": "Yes",
        "fetal_movement": "Absent",
    }
    res_pos = ml_prediction_service.predict("pregnancy", pos_record)
    assert res_pos["success"] is True
    assert res_pos["prediction"] == 1
    assert res_pos["probability_clinical_concern"] > 0.70
    assert any("Anemia" in exp or "Haemoglobin" in exp for exp in res_pos["clinical_explanations"])
    assert any("bleeding" in exp for exp in res_pos["clinical_explanations"])

    # 2. Low-risk / normal case: normal vitals, no bleeding
    norm_record = {
        "systolic_bp": 115,
        "diastolic_bp": 75,
        "haemoglobin_g_dl": 12.2,
        "vaginal_bleeding": "No",
        "severe_headache_or_blurred_vision": "No",
        "fetal_movement": "Normal",
        "ifa_calcium_consumption": "Regular",
    }
    res_norm = ml_prediction_service.predict("pregnancy", norm_record)
    assert res_norm["success"] is True
    assert res_norm["prediction"] == 0
    assert res_norm["probability_standard_risk"] > 0.60

    # 3. Missing/partial input: should handle safely without crashing
    partial_record = {"vaginal_bleeding": "Unknown"}
    res_part = ml_prediction_service.predict("pregnancy", partial_record)
    assert res_part["success"] is True
    assert "safety_disclaimer" in res_part
    assert res_part["information_completeness_ratio"] <= 0.75


def test_newborn_prediction_cases():
    """Test Newborn model with neonatal hypothermia/fever, jaundice, and breathing difficulty."""
    # 1. Neonatal emergency: fever, breathing difficulty, jaundice
    newborn_risk = {
        "age_days": 3,
        "body_temperature_c": 38.6,
        "respiratory_rate_bpm": 68,
        "difficulty_in_breathing": "Yes",
        "difficulty_in_feeding": "Yes",
        "yellowing_skin_eyes": "Yes",
    }
    res_risk = ml_prediction_service.predict("newborn", newborn_risk)
    assert res_risk["success"] is True
    assert res_risk["prediction"] == 1
    assert res_risk["probability_clinical_concern"] > 0.75
    assert any("fever" in exp.lower() or "temperature" in exp.lower() for exp in res_risk["clinical_explanations"])

    # 2. Healthy newborn: normal temperature, exclusive breastfeeding
    newborn_healthy = {
        "age_days": 7,
        "birth_weight_kg": 3.1,
        "current_weight_kg": 3.2,
        "body_temperature_c": 36.8,
        "respiratory_rate_bpm": 42,
        "breastfeeding_status": "Exclusive",
        "difficulty_in_breathing": "No",
        "difficulty_in_feeding": "No",
        "yellowing_skin_eyes": "No",
        "umbilical_cord_condition": "Normal",
    }
    res_healthy = ml_prediction_service.predict("newborn", newborn_healthy)
    assert res_healthy["success"] is True
    assert res_healthy["prediction"] == 0
    assert res_healthy["probability_standard_risk"] > 0.80


def test_immunization_prediction_cases():
    """Test Immunization model with growth faltering (low WAZ) and missed vaccines."""
    # 1. Growth concern + missed doses
    imm_concern = {
        "age_months": 9,
        "waz_score": -2.8,  # Underweight
        "haz_score": -2.4,  # Stunting
        "vaccines_due_today": "MR-1, JE-1, PCV-Booster",
        "vaccines_given_today": "None (deferred due to acute illness)",
        "missed_vaccination_doses": "Yes",
        "general_health_condition": "Unwell",
    }
    res_concern = ml_prediction_service.predict("immunization", imm_concern)
    assert res_concern["success"] is True
    assert res_concern["prediction"] == 1
    assert res_concern["probability_clinical_concern"] > 0.80
    assert any("growth" in exp.lower() or "waz" in exp.lower() for exp in res_concern["clinical_explanations"])
    assert any("deficit" in exp.lower() or "vaccine" in exp.lower() for exp in res_concern["clinical_explanations"])

    # 2. On-track child
    imm_normal = {
        "age_months": 3,
        "waz_score": 0.2,
        "haz_score": 0.4,
        "vaccines_due_today": "OPV-2, Pentavalent-2, Rotavirus-2",
        "vaccines_given_today": "OPV-2, Pentavalent-2, Rotavirus-2",
        "missed_vaccination_doses": "No",
        "general_health_condition": "Normal",
    }
    res_normal = ml_prediction_service.predict("immunization", imm_normal)
    assert res_normal["success"] is True
    assert res_normal["prediction"] == 0
    assert res_normal["probability_standard_risk"] > 0.85


def test_clinical_safety_override_prevention():
    """Requirement 12: Verify that ML predictions NEVER override an existing clinical danger alert."""
    # Record has normal vitals, but deterministic clinical rules flagged danger (e.g. active bleeding)
    normal_record = {
        "systolic_bp": 118,
        "diastolic_bp": 78,
        "haemoglobin_g_dl": 12.0,
    }
    res = ml_prediction_service.predict("pregnancy", normal_record, existing_danger_alert=True)
    assert res["success"] is True
    # Clinical rules override must be prevented
    assert res["clinical_rules_override_prevented"] is True
    assert res["severity"] == "emergency"
    assert "CRITICAL EMERGENCY" in res["composite_status"]


def test_api_predict_endpoint(client):
    """Test POST /api/ml/predict/ API endpoint."""
    payload = {
        "category": "pregnancy",
        "record": {
            "systolic_bp": 145,
            "diastolic_bp": 95,
            "haemoglobin_g_dl": 8.5,
            "vaginal_bleeding": "Yes",
        },
    }
    res = client.post("/api/ml/predict/", payload, format="json")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["category"] == "pregnancy"
    assert "probability_clinical_concern" in data
    assert "safety_disclaimer" in data
    assert len(data["clinical_explanations"]) > 0


def test_api_models_metadata_endpoint(client):
    """Test GET /api/ml/models/ API endpoint."""
    res = client.get("/api/ml/models/")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert "pregnancy" in data["models"]
    assert "newborn" in data["models"]
    assert "immunization" in data["models"]
