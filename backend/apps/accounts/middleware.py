import logging
from services.mongodb_service import set_current_db_name, MongoDBService
from apps.accounts.views import _active_tokens, DEMO_USERS

logger = logging.getLogger(__name__)

PRIMARY_ACCOUNTS = {
    "prakajayavel1994@gmail.com",
    "asha001@ashavoice.in",
    "asha002@ashavoice.in",
    "asha003@ashavoice.in",
    "asha004@ashavoice.in",
    "asha005@ashavoice.in",
    "ASHA001",
    "ASHA002",
    "ASHA003",
    "ASHA004",
    "ASHA005",
    "ASHA106",  # prakajayavel1994@gmail.com worker_id
}


def resolve_db_name_for_user(user: dict) -> str:
    """
    Returns 'Hasha' for prakajayavel1994@gmail.com and legacy demo accounts (existing database).
    For any newly created account, returns a dedicated fresh database 'Hasha_<worker_id>'.
    """
    if not user:
        return "Hasha"
    email = str(user.get("email", "")).strip().lower()
    worker_id = str(user.get("worker_id", "")).strip().upper()
    explicit_db = user.get("db_name")
    if explicit_db:
        return explicit_db
    if email in PRIMARY_ACCOUNTS or worker_id in PRIMARY_ACCOUNTS:
        return "Hasha"
    clean_wid = worker_id.lower().replace("-", "_") if worker_id else "fresh"
    return f"Hasha_{clean_wid}"


class TenantDatabaseMiddleware:
    """
    Routes database queries based on the authenticated ASHA Worker.
    prakajayavel1994@gmail.com (and ASHA001) accesses the existing database ('Hasha').
    Newly created accounts get a fresh, isolated database so other workers' patients are never exposed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        db_name = None

        # 1. Check Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()
            user = _active_tokens.get(token)
            if user:
                db_name = resolve_db_name_for_user(user)

        # 2. Check X-User-Email / X-Worker-Id headers as fallback
        if not db_name:
            email_h = request.headers.get("X-User-Email", "").strip().lower()
            wid_h = request.headers.get("X-Worker-Id", "").strip().upper()
            if email_h or wid_h:
                if email_h in PRIMARY_ACCOUNTS or wid_h in PRIMARY_ACCOUNTS:
                    db_name = "Hasha"
                else:
                    db = MongoDBService()
                    u = None
                    if email_h:
                        u = db.find_one("users", {"email": email_h})
                    if not u and wid_h:
                        u = db.find_one("users", {"worker_id": wid_h})
                    if u:
                        db_name = resolve_db_name_for_user(u)
                    elif wid_h:
                        db_name = f"Hasha_{wid_h.lower().replace('-', '_')}"

        if not db_name:
            db_name = "Hasha"

        set_current_db_name(db_name)
        try:
            return self.get_response(request)
        finally:
            set_current_db_name(None)
