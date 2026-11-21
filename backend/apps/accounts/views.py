"""
Authentication views for ASHA Voice.
Supports both registered ASHA workers (MongoDB Atlas) and legacy demo accounts.
"""
import uuid
import re
import hashlib
import logging
from datetime import datetime, timezone
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import MongoDBService

logger = logging.getLogger(__name__)

# Simple in-memory token store: token -> user_dict
_active_tokens = {}

# Demo ASHA worker accounts (retained for demo/testing compatibility)
DEMO_USERS = {
    "ASHA001": {
        "worker_id": "ASHA001",
        "email": "asha001@ashavoice.in",
        "mobile_number": "9876543210",
        "name": "Priya Sundaram",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Chennai",
        "phc": "Tambaram PHC",
        "language": "ta",
        "db_name": "Hasha",
    },
    "ASHA106": {
        "worker_id": "ASHA106",
        "email": "prakajayavel1994@gmail.com",
        "mobile_number": "7339223026",
        "name": "Prakash J",
        "password_hash": make_password("123456"),
        "role": "asha_worker",
        "district": "Chennai",
        "phc": "Primary Health Centre",
        "language": "ta",
        "db_name": "Hasha",
    },
    "ASHA002": {
        "worker_id": "ASHA002",
        "email": "asha002@ashavoice.in",
        "mobile_number": "9876543211",
        "name": "Meena Krishnan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Coimbatore",
        "phc": "Singanallur PHC",
        "language": "ta",
        "db_name": "Hasha",
    },
    "ASHA003": {
        "worker_id": "ASHA003",
        "email": "asha003@ashavoice.in",
        "mobile_number": "9876543212",
        "name": "Lakshmi Rajan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Madurai",
        "phc": "Thirunagar PHC",
        "language": "ta",
        "db_name": "Hasha",
    },
    "ASHA004": {
        "worker_id": "ASHA004",
        "email": "asha004@ashavoice.in",
        "mobile_number": "9876543213",
        "name": "Kavitha Murugan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Salem",
        "phc": "Hasthampatti PHC",
        "language": "ta",
        "db_name": "Hasha",
    },
    "ASHA005": {
        "worker_id": "ASHA005",
        "email": "asha005@ashavoice.in",
        "mobile_number": "9876543214",
        "name": "Revathi Natarajan",
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest(),
        "role": "asha_worker",
        "district": "Trichy",
        "phc": "Srirangam PHC",
        "language": "ta",
        "db_name": "Hasha",
    },
}

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
MOBILE_REGEX = re.compile(r'^[6-9]\d{9}$')


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifies password using PBKDF2 or legacy SHA-256 for demo accounts."""
    if not plain_password or not stored_hash:
        return False
    try:
        # PBKDF2 check
        if check_password(plain_password, stored_hash):
            return True
    except Exception:
        pass
    # Legacy SHA-256 fallback (used by demo accounts)
    legacy_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    return legacy_hash == stored_hash


def _get_mongodb():
    return MongoDBService()


def find_user_by_identifier(identifier: str):
    """Find user by email, worker_id, or mobile number in DB and DEMO_USERS."""
    if not identifier:
        return None
    raw = identifier.strip()
    clean_lower = raw.lower()
    clean_upper = raw.upper()

    # 1. Check DEMO_USERS first
    if clean_upper in DEMO_USERS:
        return DEMO_USERS[clean_upper]
    for u in DEMO_USERS.values():
        if u.get("email", "").lower() == clean_lower or u.get("mobile_number") == raw:
            return u

    # 2. Check MongoDB users collection
    db = _get_mongodb()
    try:
        # Check by email
        user = db.find_one("users", {"email": clean_lower})
        if user:
            return user
        # Check by worker_id
        user = db.find_one("users", {"worker_id": clean_upper})
        if user:
            return user
        # Check by mobile_number
        user = db.find_one("users", {"mobile_number": raw})
        if user:
            return user
    except Exception as e:
        logger.error(f"Error querying users in MongoDB: {e}")

    return None


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_view(request):
    """
    ASHA Worker Signup.
    Required fields: email, password, mobile_number
    Optional fields: name, district, phc, language
    """
    email = str(request.data.get("email", "")).strip().lower()
    password = str(request.data.get("password", ""))
    mobile_number = str(request.data.get("mobile_number", "")).strip()
    name = str(request.data.get("name", "")).strip()
    district = str(request.data.get("district", "Chennai")).strip()
    phc = str(request.data.get("phc", "Primary Health Centre")).strip()
    language = str(request.data.get("language", "ta")).strip()

    # Field presence validation
    if not email:
        return Response({"error": "Email ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not password:
        return Response({"error": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not mobile_number:
        return Response({"error": "ASHA Worker Mobile Number is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Email format validation
    if not EMAIL_REGEX.match(email):
        return Response({"error": "Please enter a valid Email ID."}, status=status.HTTP_400_BAD_REQUEST)

    # Mobile format validation (10 digits starting with 6-9)
    # Strip any leading +91 or 0 if present
    clean_mobile = mobile_number
    if clean_mobile.startswith("+91"):
        clean_mobile = clean_mobile[3:]
    elif clean_mobile.startswith("91") and len(clean_mobile) == 12:
        clean_mobile = clean_mobile[2:]
    elif clean_mobile.startswith("0") and len(clean_mobile) == 11:
        clean_mobile = clean_mobile[1:]

    if not MOBILE_REGEX.match(clean_mobile):
        return Response(
            {"error": "Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Password length validation
    if len(password) < 6:
        return Response(
            {"error": "Password must be at least 6 characters long."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check for duplicate email or mobile number
    db = _get_mongodb()

    # Check email uniqueness in DEMO_USERS
    for u in DEMO_USERS.values():
        if u.get("email", "").lower() == email:
            return Response(
                {"error": "An account with this Email ID already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if u.get("mobile_number") == clean_mobile:
            return Response(
                {"error": "An account with this Mobile Number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Check in MongoDB
    try:
        existing_email = db.find_one("users", {"email": email})
        if existing_email:
            return Response(
                {"error": "An account with this Email ID already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing_mobile = db.find_one("users", {"mobile_number": clean_mobile})
        if existing_mobile:
            return Response(
                {"error": "An account with this Mobile Number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        logger.error(f"Error checking duplicate user in MongoDB: {e}")

    # Generate sequential or unique worker_id
    try:
        user_count = len(db.find_all("users", limit=1000))
    except Exception:
        user_count = 0
    worker_id = f"ASHA{100 + user_count + 1}"

    # Double check worker_id uniqueness
    while db.find_one("users", {"worker_id": worker_id}) or worker_id in DEMO_USERS:
        user_count += 1
        worker_id = f"ASHA{100 + user_count + 1}"

    # Securely hash password using PBKDF2-SHA256
    hashed_pw = make_password(password)

    user_name = name or email.split("@")[0].replace(".", " ").capitalize()

    # Routing: prakajayavel1994@gmail.com uses existing 'Hasha' database.
    # Newly registered accounts get a fresh isolated database 'Hasha_<worker_id>'.
    if email == "prakajayavel1994@gmail.com" or worker_id in ("ASHA001", "ASHA106"):
        user_db_name = "Hasha"
    else:
        user_db_name = f"Hasha_{worker_id.lower()}"

    new_user = {
        "worker_id": worker_id,
        "email": email,
        "mobile_number": clean_mobile,
        "name": user_name,
        "password_hash": hashed_pw,
        "role": "asha_worker",
        "district": district,
        "phc": phc,
        "language": language,
        "db_name": user_db_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        db.insert("users", new_user)
    except Exception as e:
        logger.error(f"Failed to persist user in MongoDB: {e}")
        return Response(
            {"error": "Failed to create account due to database error. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Issue session token
    token = str(uuid.uuid4())
    safe_user = {k: v for k, v in new_user.items() if k not in ("password_hash", "_id")}
    _active_tokens[token] = safe_user

    return Response(
        {
            "token": token,
            "user": safe_user,
            "message": "Account created successfully.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login endpoint.
    Accepts email or worker_id and password.
    Works for both registered MongoDB users and demo accounts.
    """
    # Accept 'email', 'worker_id', or 'identifier'
    identifier = (
        request.data.get("email")
        or request.data.get("worker_id")
        or request.data.get("identifier")
        or ""
    ).strip()
    password = request.data.get("password", "")

    if not identifier:
        return Response(
            {"error": "Please enter your Email ID or Worker ID."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not password:
        return Response(
            {"error": "Please enter your password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = find_user_by_identifier(identifier)
    if not user:
        return Response(
            {
                "error": "Invalid email or password.",
                "detail": "No account found matching the provided credentials.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    stored_hash = user.get("password_hash", "")
    if not verify_password(password, stored_hash):
        return Response(
            {
                "error": "Invalid email or password.",
                "detail": "Password does not match.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token = str(uuid.uuid4())
    if "db_name" not in user:
        if user.get("email") == "prakajayavel1994@gmail.com" or user.get("worker_id") in ("ASHA001", "ASHA106"):
            user["db_name"] = "Hasha"
        else:
            user["db_name"] = f"Hasha_{user.get('worker_id', 'fresh').lower()}"
    safe_user = {k: v for k, v in user.items() if k not in ("password_hash", "_id")}
    _active_tokens[token] = safe_user

    return Response({
        "token": token,
        "user": safe_user,
        "message": "Login successful.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    _active_tokens.pop(token, None)
    return Response({"message": "Logged out successfully"})


@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    user = _active_tokens.get(token)
    if not user:
        return Response(
            {"error": "Not authenticated"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response({"user": user})


def get_current_user(request):
    """Helper to get user from token. Returns None if not authenticated."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    return _active_tokens.get(token)
