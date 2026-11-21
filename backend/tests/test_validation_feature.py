"""
Tests for mandatory field validation feature.
Run with: cd backend && venv/Scripts/python -m pytest tests/test_validation_feature.py -v
"""
import sys
import os
import pytest

# Allow direct import of services without Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Minimal Django setup ────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

# ─── Imports ─────────────────────────────────────────────────────────────────
from services.validation_service import ValidationService, MANDATORY_FIELDS
from services.visit_session_service import VisitSessionService


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def vs():
    return ValidationService()


@pytest.fixture
def session():
    return VisitSessionService()


def _complete_pregnancy():
    return {
        "beneficiary_name": "Lakshmi",
        "visit_type": "pregnancy",
        "pregnancy_month": 7,
        "weight_kg": 55.0,
        "confidence_score": 0.9,
    }


def _complete_newborn():
    return {
        "beneficiary_name": "Baby Meena",
        "visit_type": "newborn",
        "weight_kg": 3.1,
        "confidence_score": 0.9,
    }


def _complete_immunisation():
    return {
        "beneficiary_name": "Ravi",
        "visit_type": "immunisation",
        "vaccinations": ["BCG", "OPV"],
        "confidence_score": 0.9,
    }


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: All mandatory fields provided — record is ready to save
# ═══════════════════════════════════════════════════════════════════════════

def test_all_mandatory_fields_provided(vs):
    """TEST 1: Complete record passes validation and is ready to save."""
    record = _complete_pregnancy()
    missing = vs.get_missing_mandatory_fields(record)
    assert missing == [], f"Expected no missing fields, got: {missing}"

    ready, reasons = vs.is_ready_to_save(record)
    assert ready is True, f"Expected ready=True, got reasons: {reasons}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: One mandatory field missing — record must NOT be saved
# ═══════════════════════════════════════════════════════════════════════════

def test_one_mandatory_field_missing(vs):
    """TEST 2: Record with one missing field is blocked from saving."""
    record = _complete_pregnancy()
    del record["weight_kg"]  # remove one mandatory field

    missing = vs.get_missing_mandatory_fields(record)
    assert "weight_kg" in missing, f"Expected weight_kg in missing, got: {missing}"
    assert len(missing) == 1

    ready, reasons = vs.is_ready_to_save(record)
    assert ready is False
    assert any("weight_kg" in r for r in reasons), f"Reason should mention weight_kg: {reasons}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Multiple mandatory fields missing
# ═══════════════════════════════════════════════════════════════════════════

def test_multiple_mandatory_fields_missing(vs):
    """TEST 3: Record with multiple missing fields — all reported, save blocked."""
    record = {
        "visit_type": "pregnancy",
        "confidence_score": 0.9,
        # beneficiary_name, pregnancy_month, weight_kg all missing
    }
    missing = vs.get_missing_mandatory_fields(record)
    assert "beneficiary_name" in missing
    assert "pregnancy_month" in missing
    assert "weight_kg" in missing

    ready, _ = vs.is_ready_to_save(record)
    assert ready is False


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Voice correction — field is updated, old value not retained
# ═══════════════════════════════════════════════════════════════════════════

def test_voice_correction_updates_field(session):
    """TEST 4: Draft field update replaces old value, does not retain both."""
    initial = _complete_newborn()
    initial["weight_kg"] = 2.8  # intentionally wrong

    draft_id = session.create_draft(initial)
    draft = session.get_draft(draft_id)
    assert draft["weight_kg"] == 2.8

    # Correction: replace with 2.6
    updated = session.update_draft(draft_id, {"weight_kg": 2.6})
    assert updated["weight_kg"] == 2.6, "Updated value should be 2.6"
    assert updated["weight_kg"] != 2.8, "Old value must not be retained"

    session.discard_draft(draft_id)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Invalid numerical value — validation must flag it
# ═══════════════════════════════════════════════════════════════════════════

def test_invalid_weight_flagged(vs):
    """TEST 5: Weight outside valid range causes validation error."""
    record = _complete_pregnancy()
    record["weight_kg"] = 999.0  # out of range

    valid, errors = vs.validate(record)
    assert valid is False
    assert any("999" in e or "Weight" in e for e in errors), f"Errors: {errors}"


def test_invalid_pregnancy_month_flagged(vs):
    """TEST 5b: Pregnancy month outside 1-9 causes validation error."""
    record = _complete_pregnancy()
    record["pregnancy_month"] = 12  # out of range

    valid, errors = vs.validate(record)
    assert valid is False
    assert any("12" in e or "Pregnancy month" in e for e in errors), f"Errors: {errors}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Changing a previously confirmed field — draft update
# ═══════════════════════════════════════════════════════════════════════════

def test_field_update_re_validates(vs, session):
    """TEST 6: After updating a field in a draft, re-validation runs correctly."""
    record = _complete_pregnancy()
    draft_id = session.create_draft(record)

    # Introduce an invalid value
    session.update_draft(draft_id, {"pregnancy_month": 11})
    draft = session.get_draft(draft_id)
    valid, errors = vs.validate(draft)
    assert valid is False

    # Fix it
    session.update_draft(draft_id, {"pregnancy_month": 7})
    draft = session.get_draft(draft_id)
    ready, reasons = vs.is_ready_to_save(draft)
    assert ready is True, f"Should be ready after fix. Reasons: {reasons}"

    session.discard_draft(draft_id)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Danger sign detected — does not suppress save validation
# ═══════════════════════════════════════════════════════════════════════════

def test_danger_sign_does_not_bypass_validation(vs):
    """TEST 7: Danger flag does not make an incomplete record ready to save."""
    record = {
        "visit_type": "pregnancy",
        "danger_flag": True,
        "danger_signs": ["Bleeding during pregnancy"],
        "confidence_score": 0.9,
        # Missing beneficiary_name, pregnancy_month, weight_kg
    }
    ready, reasons = vs.is_ready_to_save(record)
    assert ready is False, "Danger flag must not bypass mandatory field validation"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 8: ASHA worker does not confirm — draft stays unsaved
# ═══════════════════════════════════════════════════════════════════════════

def test_draft_not_saved_without_confirm(session):
    """TEST 8: Draft is never saved to DB unless mark_saved() is called."""
    record = _complete_pregnancy()
    draft_id = session.create_draft(record)
    draft = session.get_draft(draft_id)

    assert draft["is_saved"] is False
    assert draft.get("db_id") is None

    session.discard_draft(draft_id)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 9: Duplicate save prevention
# ═══════════════════════════════════════════════════════════════════════════

def test_duplicate_save_prevented(vs, session):
    """TEST 9: Saving an already-saved record is blocked."""
    record = _complete_pregnancy()
    draft_id = session.create_draft(record)

    # Simulate successful save
    session.mark_saved(draft_id, "fake-db-id-123")
    draft = session.get_draft(draft_id)

    assert draft["is_saved"] is True

    ready, reasons = vs.is_ready_to_save(draft)
    assert ready is False
    assert any("already" in r.lower() or "saved" in r.lower() for r in reasons), \
        f"Should mention already saved: {reasons}"

    session.discard_draft(draft_id)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 10: All fields collected but confirmation refused — draft persists
# ═══════════════════════════════════════════════════════════════════════════

def test_no_save_on_refused_confirm(session, vs):
    """TEST 10: Complete draft remains unsaved when confirmation is withheld."""
    record = _complete_pregnancy()
    draft_id = session.create_draft(record)
    draft = session.get_draft(draft_id)

    # Validate — should be ready
    ready, _ = vs.is_ready_to_save(draft)
    assert ready is True

    # Worker refuses — we do NOT call mark_saved
    draft_after = session.get_draft(draft_id)
    assert draft_after["is_saved"] is False, "Draft must stay unsaved when confirmation is refused"

    session.discard_draft(draft_id)


# ═══════════════════════════════════════════════════════════════════════════
# Additional: mandatory fields by visit type
# ═══════════════════════════════════════════════════════════════════════════

def test_immunisation_requires_vaccinations(vs):
    """Immunisation visit without vaccinations list fails validation."""
    record = {
        "beneficiary_name": "Ravi",
        "visit_type": "immunisation",
        "vaccinations": [],   # empty list = missing
        "confidence_score": 0.9,
    }
    missing = vs.get_missing_mandatory_fields(record)
    assert "vaccinations" in missing

    ready, _ = vs.is_ready_to_save(record)
    assert ready is False


def test_household_minimal_fields(vs):
    """Household visit only requires beneficiary_name and visit_type."""
    record = {
        "beneficiary_name": "Saroja",
        "visit_type": "household",
        "confidence_score": 0.9,
    }
    missing = vs.get_missing_mandatory_fields(record)
    assert missing == [], f"Household should require only name+type, got: {missing}"


def test_field_prompt_generated_for_missing(vs):
    """get_field_prompt returns non-empty string for every mandatory field."""
    for vtype_fields in MANDATORY_FIELDS.values():
        for field in vtype_fields:
            prompt = vs.get_field_prompt(field)
            assert isinstance(prompt, str) and len(prompt) > 0, \
                f"Empty prompt for field: {field}"


def test_draft_discard_cleans_up(session):
    """discard_draft removes the draft from memory."""
    draft_id = session.create_draft({"visit_type": "household"})
    assert session.get_draft(draft_id) is not None
    session.discard_draft(draft_id)
    assert session.get_draft(draft_id) is None


def test_readback_text_includes_all_fields(vs):
    """build_readback_text includes all present field values."""
    record = _complete_pregnancy()
    record["anc_completed"] = True
    record["ifa_given"] = True
    record["next_visit_date"] = "2026-12-01"

    text = vs.build_readback_text(record)
    assert "Lakshmi" in text
    assert "pregnancy" in text.lower()
    assert "7" in text
    assert "55" in text
    assert "ANC" in text
    assert "IFA" in text
    assert "2026-12-01" in text
    assert "confirm" in text.lower() or "save" in text.lower()
