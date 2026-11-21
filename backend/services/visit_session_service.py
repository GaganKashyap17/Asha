"""
Visit Session Service — in-memory draft manager for ASHA Voice.

Holds temporary (draft) visit records until ALL mandatory fields are
collected, validated, and explicitly confirmed by the ASHA worker.
Records are NEVER written to MongoDB until confirmation.
"""
import uuid
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class VisitSessionService:
    """
    Thread-safe in-memory store for draft visit records.

    Lifecycle:
        create_draft()          → returns draft_id
        update_draft()          → merge new fields into draft
        get_draft()             → retrieve current draft state
        discard_draft()         → remove draft (cancel / after save)
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_draft(self, initial_data: dict, worker_id: str = "unknown") -> str:
        """Create a new draft and return its draft_id."""
        draft_id = str(uuid.uuid4())
        draft = {
            "draft_id": draft_id,
            "worker_id": worker_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **initial_data,
            "confirmation_status": "draft",
            "is_saved": False,
        }
        with self._lock:
            self._store[draft_id] = draft
        logger.info(f"Draft created: {draft_id}")
        return draft_id

    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the draft, or None if not found."""
        with self._lock:
            draft = self._store.get(draft_id)
            return dict(draft) if draft else None

    def update_draft(self, draft_id: str, fields: dict) -> Optional[Dict[str, Any]]:
        """
        Merge *fields* into existing draft.
        Returns updated draft copy, or None if draft not found.
        """
        with self._lock:
            draft = self._store.get(draft_id)
            if draft is None:
                logger.warning(f"update_draft: draft {draft_id} not found")
                return None
            protected = {"draft_id", "worker_id", "created_at", "is_saved"}
            for k, v in fields.items():
                if k not in protected and v is not None:
                    draft[k] = v
            draft["updated_at"] = datetime.now(timezone.utc).isoformat()
            return dict(draft)

    def mark_saved(self, draft_id: str, db_id: str) -> bool:
        """Mark draft as saved after successful MongoDB insert."""
        with self._lock:
            draft = self._store.get(draft_id)
            if draft is None:
                return False
            draft["is_saved"] = True
            draft["db_id"] = db_id
            draft["confirmation_status"] = "confirmed"
            return True

    def discard_draft(self, draft_id: str) -> bool:
        """Remove draft from memory."""
        with self._lock:
            existed = draft_id in self._store
            self._store.pop(draft_id, None)
        if existed:
            logger.info(f"Draft discarded: {draft_id}")
        return existed

    def list_drafts(self, worker_id: Optional[str] = None) -> List[dict]:
        """List all drafts, optionally filtered by worker."""
        with self._lock:
            drafts = list(self._store.values())
        if worker_id:
            drafts = [d for d in drafts if d.get("worker_id") == worker_id]
        return [dict(d) for d in drafts]

    def draft_count(self) -> int:
        with self._lock:
            return len(self._store)


# Singleton
visit_session_service = VisitSessionService()
