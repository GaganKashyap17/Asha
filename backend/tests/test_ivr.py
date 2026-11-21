"""
Tests for IVR Reminder subsystem.
Validates status, beneficiary merging, initiate calls, 24h duplication, and history.
"""
import os
import sys
import pytest
from rest_framework.test import APIClient
from rest_framework import status

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from services.mongodb_service import mongodb_service


@pytest.fixture(autouse=True)
def ensure_db():
    mongodb_service.ensure_connected()
    yield


@pytest.fixture
def client():
    return APIClient(SERVER_NAME="localhost")


def test_ivr_status(client):
    response = client.get("/api/ivr/status/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "operational"
    assert data["mode"] == "simulated"
    assert "supported_languages" in data
    assert "ta" in data["supported_languages"]


def test_ivr_beneficiaries(client):
    response = client.get("/api/ivr/beneficiaries/?tomorrow_only=true")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "results" in data
    assert data["count"] >= 1
    first = data["results"][0]
    assert "beneficiary_name" in first
    assert "mobile_number" in first
    assert "visit_date" in first
    assert "visit_type" in first


def test_ivr_initiate_call_success(client):
    payload = {
        "beneficiary_name": "Divya Test",
        "mobile_number": "9199887766",
        "visit_date": "2026-11-23",
        "visit_type": "Child Immunization Revisit",
        "language": "ta",
        "followup_id": "fu-test-999",
        "beneficiary_id": "IMM-TEST-999",
    }
    response = client.post("/api/ivr/initiate/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["demo"] is True
    assert "call" in data
    call = data["call"]
    assert call["beneficiary_name"] == "Divya Test"
    assert call["mobile_number"] == "9199887766"
    assert call["language"] == "ta"
    assert call["status"] in ["completed", "busy", "no_answer", "failed"]


def test_ivr_initiate_duplicate_prevention(client):
    payload = {
        "beneficiary_name": "Priya Rajan",
        "mobile_number": "7339223026",
        "visit_date": "2026-11-23",
        "visit_type": "ANC Check-up / Maternal Vitals",
        "language": "en",
        "followup_id": "fu-2026-001",
    }
    response = client.post("/api/ivr/initiate/", payload, format="json")
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert data["error"] == "duplicate_call"


def test_ivr_initiate_validation_error(client):
    payload = {
        "beneficiary_name": "Incomplete Record",
        "visit_date": "2026-11-23",
        "visit_type": "Health Revisit",
    }
    response = client.post("/api/ivr/initiate/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_ivr_call_history(client):
    response = client.get("/api/ivr/history/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "results" in data
    assert data["count"] >= 1
    latest = data["results"][0]
    assert "call_id" in latest
    assert "status" in latest
    assert "reminder_message" in latest
