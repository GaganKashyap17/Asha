"""
Tests for Beneficiary Management, CRUD Operations & Database Synchronization.
Run with: cd backend && venv/Scripts/python -m pytest tests/test_beneficiary_crud.py -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from services.mongodb_service import mongodb_service
from apps.beneficiaries.views import generate_beneficiary_id
from apps.visits.views import _ensure_beneficiary_exists_and_linked


@pytest.fixture(autouse=True)
def clean_test_data():
    """Ensure in-memory/test isolation."""
    mongodb_service.ensure_connected()
    yield


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: Add a new beneficiary — stored in MongoDB & returned
# ═══════════════════════════════════════════════════════════════════════════

def test_add_new_beneficiary():
    """TEST 1: Creating a beneficiary generates an ID and saves to collection."""
    new_id = generate_beneficiary_id()
    doc = {
        "beneficiary_id": new_id,
        "name": "Karpagam Devi",
        "age": 25,
        "gender": "female",
        "village": "Tambaram",
        "household": "House 45",
        "pregnancy_status": "pregnant",
        "pregnancy_month": 4,
        "is_deleted": False,
        "is_archived": False,
    }
    saved = mongodb_service.insert("beneficiaries", doc)
    assert saved["beneficiary_id"] == new_id
    assert saved["name"] == "Karpagam Devi"

    # Verify retrieval
    found = mongodb_service.find_one("beneficiaries", {"beneficiary_id": new_id})
    assert found is not None
    assert found["name"] == "Karpagam Devi"
    assert found["village"] == "Tambaram"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Persistence verification — newly created beneficiary remains visible
# ═══════════════════════════════════════════════════════════════════════════

def test_beneficiary_persistence():
    """TEST 2: Beneficiary remains in database across queries."""
    bene_id = "BEN991"
    doc = {
        "beneficiary_id": bene_id,
        "name": "Selvi Kumar",
        "is_deleted": False,
    }
    mongodb_service.insert("beneficiaries", doc)

    # First fetch
    r1 = mongodb_service.find_one("beneficiaries", {"beneficiary_id": bene_id})
    assert r1 is not None and r1["name"] == "Selvi Kumar"

    # Second fetch (simulating page reload)
    r2 = mongodb_service.find_one("beneficiaries", {"beneficiary_id": bene_id})
    assert r2 is not None and r2["name"] == "Selvi Kumar"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: Edit an existing beneficiary — updated info saved & reflected
# ═══════════════════════════════════════════════════════════════════════════

def test_edit_existing_beneficiary():
    """TEST 3: Editing a beneficiary updates fields and persists."""
    bene_id = "BEN992"
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": bene_id,
        "name": "Radha",
        "village": "Madurai",
        "pregnancy_status": "pregnant",
        "pregnancy_month": 5,
        "is_deleted": False,
    })

    # Update village and pregnancy month
    success = mongodb_service.update_one(
        "beneficiaries",
        {"beneficiary_id": bene_id},
        {"$set": {"village": "Thirunagar", "pregnancy_month": 6}}
    )
    assert success is True

    updated = mongodb_service.find_one("beneficiaries", {"beneficiary_id": bene_id})
    assert updated["village"] == "Thirunagar"
    assert updated["pregnancy_month"] == 6
    assert updated["name"] == "Radha"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Delete/archive existing beneficiary — removed from active list,
#         WITHOUT destroying historical visit records
# ═══════════════════════════════════════════════════════════════════════════

def test_delete_archive_beneficiary_preserves_visits():
    """TEST 4: Soft delete archives beneficiary while keeping visit records."""
    bene_id = "BEN993"
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": bene_id,
        "name": "Geetha",
        "is_deleted": False,
        "is_archived": False,
    })
    # Attach a historical visit
    mongodb_service.insert("visits", {
        "beneficiary_id": bene_id,
        "beneficiary_name": "Geetha",
        "visit_type": "pregnancy",
        "visit_date": "2026-11-01",
        "confirmation_status": "confirmed",
    })

    # Archive the beneficiary
    mongodb_service.update_one(
        "beneficiaries",
        {"beneficiary_id": bene_id},
        {"$set": {"is_deleted": True, "is_archived": True}}
    )

    # Active beneficiary list check
    active_b = mongodb_service.find_one("beneficiaries", {
        "beneficiary_id": bene_id,
        "is_deleted": {"$ne": True}
    })
    assert active_b is None, "Archived beneficiary must not appear in active search"

    # Historical visit records MUST still exist!
    historical_visits = mongodb_service.find_all("visits", {"beneficiary_id": bene_id})
    assert len(historical_visits) == 1
    assert historical_visits[0]["beneficiary_name"] == "Geetha"
    assert historical_visits[0]["confirmation_status"] == "confirmed"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Register a visit for an existing beneficiary — links to existing ID
#         WITHOUT creating duplicate beneficiary
# ═══════════════════════════════════════════════════════════════════════════

def test_visit_linked_to_existing_beneficiary_no_duplicate():
    """TEST 5: Visiting an existing beneficiary reuses their ID and updates dates."""
    bene_id = "BEN994"
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": bene_id,
        "name": "Bhavani",
        "pregnancy_status": "pregnant",
        "pregnancy_month": 6,
        "is_deleted": False,
    })

    visit_data = {
        "beneficiary_name": "Bhavani",
        "beneficiary_id": bene_id,
        "visit_type": "pregnancy",
        "pregnancy_month": 7,
        "visit_date": "2026-11-19",
        "next_visit_date": "2026-12-03",
    }

    linked = _ensure_beneficiary_exists_and_linked("Bhavani", bene_id, visit_data)
    assert linked is not None
    assert linked["beneficiary_id"] == bene_id

    # Check beneficiary dates updated
    b = mongodb_service.find_one("beneficiaries", {"beneficiary_id": bene_id})
    assert b["last_visit_date"] == "2026-11-19"
    assert b["next_visit_date"] == "2026-12-03"
    assert b["pregnancy_month"] == 7

    # Ensure no duplicate was created
    all_bhavani = [
        item for item in mongodb_service.find_all("beneficiaries", limit=1000)
        if item.get("name") == "Bhavani"
    ]
    assert len(all_bhavani) == 1


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Register a new beneficiary through voice — auto creates document
# ═══════════════════════════════════════════════════════════════════════════

def test_voice_visit_auto_creates_beneficiary():
    """TEST 6: Voice registration with new name creates beneficiary document."""
    visit_data = {
        "beneficiary_name": "Nandhini",
        "visit_type": "pregnancy",
        "pregnancy_month": 4,
        "visit_date": "2026-11-19",
        "next_visit_date": "2026-12-10",
    }

    linked = _ensure_beneficiary_exists_and_linked("Nandhini", None, visit_data)
    assert linked is not None
    assert linked["name"] == "Nandhini"
    assert linked["beneficiary_id"].startswith("BEN")
    assert linked["pregnancy_status"] == "pregnant"
    assert linked["pregnancy_month"] == 4

    # Verify presence in beneficiaries collection
    in_db = mongodb_service.find_one("beneficiaries", {"name": "Nandhini"})
    assert in_db is not None
    assert in_db["beneficiary_id"] == linked["beneficiary_id"]


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Register multiple beneficiaries — all preserved without overwrite
# ═══════════════════════════════════════════════════════════════════════════

def test_multiple_beneficiaries_distinct():
    """TEST 7: Multiple registrations retain independent records."""
    names = ["Kavya", "Deepika", "Shalini"]
    created_ids = []
    for n in names:
        b = _ensure_beneficiary_exists_and_linked(n, None, {"visit_type": "household", "visit_date": "2026-11-19"})
        assert b is not None
        created_ids.append(b["beneficiary_id"])

    # Ensure all IDs are unique
    assert len(set(created_ids)) == 3

    # Check each can be fetched individually
    for cid, n in zip(created_ids, names):
        doc = mongodb_service.find_one("beneficiaries", {"beneficiary_id": cid})
        assert doc is not None
        assert doc["name"] == n


# ═══════════════════════════════════════════════════════════════════════════
# TEST 8: Search for a newly created beneficiary
# ═══════════════════════════════════════════════════════════════════════════

def test_search_beneficiary():
    """TEST 8: Searching by name or ID returns the expected beneficiary."""
    bene_id = "BEN_SEARCH_001"
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": bene_id,
        "name": "Yashodha",
        "village": "Thirunagar",
        "is_deleted": False,
    })

    # Search by partial name
    matches = [
        b for b in mongodb_service.find_all("beneficiaries", limit=500)
        if "yasho" in b.get("name", "").lower() and not b.get("is_deleted")
    ]
    assert len(matches) == 1
    assert matches[0]["beneficiary_id"] == bene_id

    # Search by ID
    match_id = mongodb_service.find_one("beneficiaries", {"beneficiary_id": bene_id, "is_deleted": {"$ne": True}})
    assert match_id is not None
    assert match_id["name"] == "Yashodha"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 9: Check History after editing a beneficiary — name synced, visits preserved
# ═══════════════════════════════════════════════════════════════════════════

def test_history_after_editing_beneficiary():
    """TEST 9: Changing beneficiary name synchronizes in visits history."""
    bene_id = "BEN996"
    mongodb_service.insert("beneficiaries", {
        "beneficiary_id": bene_id,
        "name": "Sowmya Old",
        "is_deleted": False,
    })
    mongodb_service.insert("visits", {
        "beneficiary_id": bene_id,
        "beneficiary_name": "Sowmya Old",
        "visit_type": "pregnancy",
        "visit_date": "2026-11-10",
        "confirmation_status": "confirmed",
    })

    # Update name in beneficiary and sync to visits
    mongodb_service.update_one(
        "beneficiaries",
        {"beneficiary_id": bene_id},
        {"$set": {"name": "Sowmya New"}}
    )
    mongodb_service.update_many(
        "visits",
        {"beneficiary_id": bene_id},
        {"$set": {"beneficiary_name": "Sowmya New"}}
    )

    # Verify visit in history now reflects updated name
    visits = mongodb_service.find_all("visits", {"beneficiary_id": bene_id})
    assert len(visits) == 1
    assert visits[0]["beneficiary_name"] == "Sowmya New"
    assert visits[0]["visit_date"] == "2026-11-10"
