"""
Followup service — business logic for creating and scheduling followups.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

FOLLOWUP_RULES = {
    "pregnancy": {
        "interval_days": 14,
        "priority": "high",
        "notes": "ANC followup — check weight, BP, IFA compliance",
    },
    "newborn": {
        "interval_days": 3,
        "priority": "emergency",
        "notes": "Newborn followup — check feeding, temperature, umbilicus",
    },
    "postnatal": {
        "interval_days": 7,
        "priority": "high",
        "notes": "Postnatal followup — check mother and baby",
    },
    "immunisation": {
        "interval_days": 30,
        "priority": "medium",
        "notes": "Next immunisation due",
    },
    "household": {
        "interval_days": 30,
        "priority": "low",
        "notes": "Routine household visit",
    },
}


class FollowupService:
    """Create and manage followup records."""

    def create_followup_from_visit(self, visit: dict) -> Optional[dict]:
        """
        Generate a followup record from a confirmed visit.
        Returns the followup dict (caller saves it to DB).
        """
        from services.mongodb_service import mongodb_service

        visit_type = visit.get("visit_type", "household")
        rule = FOLLOWUP_RULES.get(visit_type, FOLLOWUP_RULES["household"])

        # Compute due date
        base = visit.get("next_visit_date")
        if base:
            try:
                due_date = datetime.strptime(base, "%Y-%m-%d").date()
            except ValueError:
                due_date = datetime.now(timezone.utc).date() + timedelta(days=rule["interval_days"])
        else:
            due_date = datetime.now(timezone.utc).date() + timedelta(days=rule["interval_days"])

        followup = {
            "visit_id": visit.get("_id") or visit.get("id"),
            "beneficiary_id": visit.get("beneficiary_id"),
            "beneficiary_name": visit.get("beneficiary_name"),
            "visit_type": visit_type,
            "due_date": due_date.isoformat(),
            "priority": "emergency" if visit.get("danger_flag") else rule["priority"],
            "status": "pending",
            "notes": rule["notes"],
            "danger_flag": visit.get("danger_flag", False),
        }

        saved = mongodb_service.insert("followups", followup)
        logger.info(
            f"Followup created for beneficiary {followup['beneficiary_id']} "
            f"due {followup['due_date']}"
        )
        return saved

    def mark_complete(self, followup_id: str, notes: str = "") -> bool:
        from services.mongodb_service import mongodb_service
        return mongodb_service.update_one(
            "followups",
            {"_id": followup_id},
            {"$set": {"status": "completed", "completion_notes": notes}},
        )

    def get_overdue(self) -> List[dict]:
        from services.mongodb_service import mongodb_service
        today = datetime.now(timezone.utc).date().isoformat()
        all_pending = mongodb_service.find_all("followups", {"status": "pending"})
        return [f for f in all_pending if f.get("due_date", "9999-12-31") < today]


# Singleton
followup_service = FollowupService()
