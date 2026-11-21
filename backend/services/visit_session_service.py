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
    Thread-safe store for draft visit records with in-memory caching
    and persistent database backup to prevent draft loss on server restarts.

    Lifecycle:
        create_draft()          → returns draft_id
        update_draft()          → merge new fields into draft
        get_draft()             → retrieve current draft state
        create_or_restore_draft()→ heal/reconstruct draft if missing
        discard_draft()         → remove draft (cancel / after save)
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_draft(self, initial_data: dict, worker_id: str = "unknown") -> str:
        """Create a new draft and return its draft_id."""
        draft_id = str(initial_data.get("draft_id") or uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        draft = {
            "draft_id": draft_id,
            "worker_id": worker_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            **initial_data,
            "confirmation_status": "draft",
            "is_saved": False,
        }
        with self._lock:
            self._store[draft_id] = draft

        try:
            from services.mongodb_service import mongodb_service
            mongodb_service.update_one("visit_drafts", {"draft_id": draft_id}, {"$set": draft})
        except Exception:
            pass

        logger.info(f"Draft created: {draft_id}")
        return draft_id

    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the draft, or restore from database if missing from memory."""
        with self._lock:
            draft = self._store.get(draft_id)
            if draft:
                return dict(draft)

        # Fallback: check persistent visit_drafts collection
        try:
            from services.mongodb_service import mongodb_service
            doc = mongodb_service.find_one("visit_drafts", {"draft_id": draft_id})
            if doc:
                clean_doc = {k: v for k, v in doc.items() if k != "_id"}
                with self._lock:
                    self._store[draft_id] = clean_doc
                return dict(clean_doc)
        except Exception:
            pass

        return None

    def create_or_restore_draft(self, draft_id: str, fields: Optional[dict] = None) -> Dict[str, Any]:
        """Auto-create or restore a draft session if server restarted or session was lost."""
        draft = self.get_draft(draft_id)
        if draft is not None:
            if fields:
                return self.update_draft(draft_id, fields) or draft
            return draft

        now_iso = datetime.now(timezone.utc).isoformat()
        new_draft = {
            "draft_id": draft_id,
            "worker_id": "ASHA001",
            "created_at": now_iso,
            "updated_at": now_iso,
            **(fields or {}),
            "confirmation_status": "draft",
            "is_saved": False,
        }
        with self._lock:
            self._store[draft_id] = new_draft

        try:
            from services.mongodb_service import mongodb_service
            mongodb_service.update_one("visit_drafts", {"draft_id": draft_id}, {"$set": new_draft})
        except Exception:
            pass

        return dict(new_draft)

    def update_draft(self, draft_id: str, fields: dict) -> Optional[Dict[str, Any]]:
        """
        Merge *fields* into existing draft.
        Auto-restores draft if missing from memory.
        """
        with self._lock:
            draft = self._store.get(draft_id)

        if draft is None:
            # Attempt to restore or auto-create
            draft = self.create_or_restore_draft(draft_id, fields)
            return dict(draft)

        protected = {"draft_id", "worker_id", "created_at", "is_saved"}
        with self._lock:
            for k, v in fields.items():
                if k not in protected and v is not None:
                    draft[k] = v
            draft["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated_copy = dict(draft)

        try:
            from services.mongodb_service import mongodb_service
            mongodb_service.update_one("visit_drafts", {"draft_id": draft_id}, {"$set": updated_copy})
        except Exception:
            pass

        return updated_copy

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
