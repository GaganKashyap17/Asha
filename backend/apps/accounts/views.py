"""
Demo authentication views for ASHA Voice.
Clearly identified as demo auth — NOT production-grade identity verification.
"""
import uuid
import hashlib
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# Simple in-memory token store (demo only)
_active_tokens = {}

# Demo ASHA worker accounts
DEMO_USERS = {
    "ASHA001": {
        "worker_id": "ASHA001",
        "name": "Priya Sundaram",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Chennai",
        "phc": "Tambaram PHC",
        "language": "ta",
    },
    "ASHA002": {
        "worker_id": "ASHA002",
        "name": "Meena Krishnan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Coimbatore",
        "phc": "Singanallur PHC",
        "language": "ta",
    },
    "ASHA003": {
        "worker_id": "ASHA003",
        "name": "Lakshmi Rajan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Madurai",
        "phc": "Thirunagar PHC",
        "language": "ta",
    },
    "ASHA004": {
        "worker_id": "ASHA004",
        "name": "Kavitha Murugan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Salem",
        "phc": "Hasthampatti PHC",
        "language": "ta",
    },
    "ASHA005": {
        "worker_id": "ASHA005",
        "name": "Revathi Natarajan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Trichy",
        "phc": "Srirangam PHC",
        "language": "ta",
    },
}


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Demo login. Returns a session token. NOT production auth."""
    worker_id = request.data.get("worker_id", "").strip().upper()
    password = request.data.get("password", "")

    user = DEMO_USERS.get(worker_id)
    if not user:
        return Response(
            {"error": "Invalid worker ID", "detail": "Demo accounts: ASHA001-ASHA005"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != user["password_hash"]:
        return Response(
            {"error": "Invalid password", "detail": "Demo password: demo123"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token = str(uuid.uuid4())
    _active_tokens[token] = worker_id
    
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return Response({
        "token": token,
        "user": safe_user,
        "message": "Demo authentication successful. This is not production-grade identity verification.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    _active_tokens.pop(token, None)
    return Response({"message": "Logged out"})


@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    worker_id = _active_tokens.get(token)
    if not worker_id:
        return Response(
            {"error": "Not authenticated"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    user = DEMO_USERS.get(worker_id, {})
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return Response({"user": safe_user})


def get_current_user(request):
    """Helper to get user from token. Returns None if not authenticated."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    worker_id = _active_tokens.get(token)
    if worker_id:
        return DEMO_USERS.get(worker_id)
    return None
