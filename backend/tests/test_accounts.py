"""
Unit tests for ASHA Worker Authentication (Signup & Signin).
Tests MongoDB persistence, PBKDF2 password hashing, validation, duplicate prevention,
and demo account backwards compatibility.
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.hashers import check_password
from services.mongodb_service import MongoDBService


@pytest.fixture(autouse=True)
def clean_users_collection():
    """Ensure a clean users collection before each test."""
    db = MongoDBService()
    # Reset in-memory or delete test users
    if db._db is not None:
        db._db.users.delete_many({"email": {"$regex": "@test.com$"}})
    else:
        db._ensure_memory()
        db._memory_store["users"] = [
            u for u in db._memory_store.get("users", [])
            if not u.get("email", "").endswith("@test.com")
        ]
    yield


@pytest.fixture
def client():
    return APIClient()


def test_signup_success(client):
    """Test creating a new ASHA worker account successfully."""
    payload = {
        "email": "priya.worker@test.com",
        "mobile_number": "9840123456",
        "password": "SecurePassword123!",
        "name": "Priya Worker",
        "district": "Chennai",
        "phc": "Tambaram PHC",
    }
    response = client.post("/api/accounts/signup/", payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert "user" in data
    user = data["user"]
    assert user["email"] == "priya.worker@test.com"
    assert user["mobile_number"] == "9840123456"
    assert user["name"] == "Priya Worker"
    assert "password_hash" not in user
    assert "password" not in user
    assert user["worker_id"].startswith("ASHA")

    # Verify stored document in MongoDB has hashed password (PBKDF2)
    db = MongoDBService()
    stored_user = db.find_one("users", {"email": "priya.worker@test.com"})
    assert stored_user is not None
    assert stored_user["password_hash"] != "SecurePassword123!"
    assert stored_user["password_hash"].startswith("pbkdf2_sha256$")
    assert check_password("SecurePassword123!", stored_user["password_hash"])


def test_signup_missing_fields(client):
    """Test validation errors when mandatory fields are missing."""
    # Missing email
    r1 = client.post("/api/accounts/signup/", {"mobile_number": "9840123456", "password": "pass"}, format="json")
    assert r1.status_code == 400
    assert "Email ID is required" in r1.json()["error"]

    # Missing password
    r2 = client.post("/api/accounts/signup/", {"email": "test@test.com", "mobile_number": "9840123456"}, format="json")
    assert r2.status_code == 400
    assert "Password is required" in r2.json()["error"]

    # Missing mobile
    r3 = client.post("/api/accounts/signup/", {"email": "test@test.com", "password": "password123"}, format="json")
    assert r3.status_code == 400
    assert "Mobile Number is required" in r3.json()["error"]


def test_signup_invalid_formats(client):
    """Test invalid email format, invalid mobile numbers, and short password."""
    # Invalid email
    r1 = client.post(
        "/api/accounts/signup/",
        {"email": "notanemail", "mobile_number": "9840123456", "password": "password123"},
        format="json",
    )
    assert r1.status_code == 400
    assert "valid Email" in r1.json()["error"]

    # Invalid mobile (starts with 5)
    r2 = client.post(
        "/api/accounts/signup/",
        {"email": "valid@test.com", "mobile_number": "5555555555", "password": "password123"},
        format="json",
    )
    assert r2.status_code == 400
    assert "10-digit Indian mobile number" in r2.json()["error"]

    # Invalid mobile (too short)
    r3 = client.post(
        "/api/accounts/signup/",
        {"email": "valid@test.com", "mobile_number": "98401", "password": "password123"},
        format="json",
    )
    assert r3.status_code == 400
    assert "10-digit Indian mobile number" in r3.json()["error"]

    # Password too short (< 6)
    r4 = client.post(
        "/api/accounts/signup/",
        {"email": "valid@test.com", "mobile_number": "9840123456", "password": "123"},
        format="json",
    )
    assert r4.status_code == 400
    assert "at least 6 characters" in r4.json()["error"]


def test_signup_duplicate_rejection(client):
    """Test that signup prevents duplicate email or mobile number."""
    payload = {
        "email": "duplicate@test.com",
        "mobile_number": "9840199999",
        "password": "Password123!",
    }
    r1 = client.post("/api/accounts/signup/", payload, format="json")
    assert r1.status_code == 201

    # Attempt same email with different mobile
    r2 = client.post(
        "/api/accounts/signup/",
        {"email": "duplicate@test.com", "mobile_number": "9840188888", "password": "Password123!"},
        format="json",
    )
    assert r2.status_code == 400
    assert "Email ID already exists" in r2.json()["error"]

    # Attempt different email with same mobile
    r3 = client.post(
        "/api/accounts/signup/",
        {"email": "another@test.com", "mobile_number": "9840199999", "password": "Password123!"},
        format="json",
    )
    assert r3.status_code == 400
    assert "Mobile Number already exists" in r3.json()["error"]


def test_login_with_registered_account(client):
    """Test login with registered email, mobile, or generated worker_id."""
    signup_payload = {
        "email": "sarah.worker@test.com",
        "mobile_number": "9123456789",
        "password": "WorkerSecret#2026",
    }
    res = client.post("/api/accounts/signup/", signup_payload, format="json")
    assert res.status_code == 201
    worker_id = res.json()["user"]["worker_id"]

    # 1. Login with email
    r_email = client.post(
        "/api/accounts/login/",
        {"email": "sarah.worker@test.com", "password": "WorkerSecret#2026"},
        format="json",
    )
    assert r_email.status_code == 200
    assert "token" in r_email.json()

    # 2. Login with worker_id
    r_worker = client.post(
        "/api/accounts/login/",
        {"worker_id": worker_id, "password": "WorkerSecret#2026"},
        format="json",
    )
    assert r_worker.status_code == 200

    # 3. Login with mobile_number
    r_mobile = client.post(
        "/api/accounts/login/",
        {"identifier": "9123456789", "password": "WorkerSecret#2026"},
        format="json",
    )
    assert r_mobile.status_code == 200

    # 4. Wrong password
    r_wrong = client.post(
        "/api/accounts/login/",
        {"email": "sarah.worker@test.com", "password": "WrongPassword"},
        format="json",
    )
    assert r_wrong.status_code == 401
    assert "Invalid email or password" in r_wrong.json()["error"]


def test_demo_account_compatibility(client):
    """Test that existing demo account (ASHA001 / demo123) works seamlessly."""
    # Login with worker_id ASHA001
    r1 = client.post(
        "/api/accounts/login/",
        {"worker_id": "ASHA001", "password": "demo123"},
        format="json",
    )
    assert r1.status_code == 200
    data = r1.json()
    assert data["user"]["worker_id"] == "ASHA001"
    assert data["user"]["name"] == "Priya Sundaram"

    # Login with demo email asha001@ashavoice.in
    r2 = client.post(
        "/api/accounts/login/",
        {"email": "asha001@ashavoice.in", "password": "demo123"},
        format="json",
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["worker_id"] == "ASHA001"


def test_auth_me_and_logout(client):
    """Test /api/accounts/me/ with and without token, and logout."""
    # Without token -> 401
    r_unauth = client.get("/api/accounts/me/")
    assert r_unauth.status_code == 401

    # Login demo
    r_login = client.post(
        "/api/accounts/login/",
        {"worker_id": "ASHA001", "password": "demo123"},
        format="json",
    )
    token = r_login.json()["token"]

    # With token -> 200
    r_me = client.get("/api/accounts/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert r_me.status_code == 200
    assert r_me.json()["user"]["worker_id"] == "ASHA001"

    # Logout
    r_logout = client.post("/api/accounts/logout/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert r_logout.status_code == 200

    # Now me should return 401
    r_me_after = client.get("/api/accounts/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert r_me_after.status_code == 401


def test_primary_account_prakash(client):
    """Test that prakajayavel1994@gmail.com / 123456 accesses the primary 'Hasha' database."""
    res = client.post(
        "/api/accounts/login/",
        {"email": "prakajayavel1994@gmail.com", "password": "123456"},
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == "prakajayavel1994@gmail.com"
    assert data["user"]["db_name"] == "Hasha"


def test_new_account_gets_fresh_database(client):
    """Test that newly registered accounts get a fresh isolated database and cannot see other patients."""
    signup_payload = {
        "email": "fresh.asha@test.com",
        "mobile_number": "9998887776",
        "password": "Password123456",
        "name": "Fresh Worker",
    }
    res = client.post("/api/accounts/signup/", signup_payload, format="json")
    assert res.status_code == 201
    user = res.json()["user"]
    token = res.json()["token"]
    assert user["db_name"].startswith("Hasha_")

    # In the fresh worker's database, list of beneficiaries is empty initially
    r_list = client.get("/api/beneficiaries/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert r_list.status_code == 200
    assert r_list.json()["count"] == 0
