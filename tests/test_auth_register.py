"""API tests for the auth registration endpoint (POST /auth/register).

Covers the registration contract end-to-end through the FastAPI test client:
- successful registration with a normal password (plus login round-trip)
- password confirmation mismatch
- password shorter than the minimum length
- overly long password handling (bcrypt 72-byte limit)
- duplicate email rejection
"""
import os
import sys
import uuid

# Make the repository root importable when running the bare `pytest` console
# script (same bootstrap as tests/test_api.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a unique test database for each test run (set before importing the app).
test_db_path = f"./test_auth_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Import everything after setting the environment variable.
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.database as auth_db  # noqa: E402
from app.api.main import app  # noqa: E402
from app.auth.database import Base  # noqa: E402

# Initialize database tables (idempotent; in a full-suite run tables already
# exist from tests/test_api.py and this is a no-op).
Base.metadata.create_all(bind=auth_db.engine)

client = TestClient(app)


def _unique_email() -> str:
    return f"deepika+{uuid.uuid4().hex[:10]}@example.com"


def test_register_success_with_normal_password():
    """A normal 10-character password registers, logs in, and leaks no hash."""
    email = _unique_email()
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Deepika",
            "password": "Deepika123",
            "password_confirm": "Deepika123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert body["user"]["full_name"] == "Deepika"
    assert "password_hash" not in body["user"]
    assert "password" not in body["user"]

    # The stored hash must verify: login round-trip with the same password.
    login = client.post("/auth/login", json={"email": email, "password": "Deepika123"})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_register_password_confirmation_mismatch():
    response = client.post(
        "/auth/register",
        json={
            "email": _unique_email(),
            "full_name": "Deepika",
            "password": "Deepika123",
            "password_confirm": "Deepika124",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Passwords do not match"


def test_register_password_too_short():
    response = client.post(
        "/auth/register",
        json={
            "email": _unique_email(),
            "full_name": "Deepika",
            "password": "abc12",
            "password_confirm": "abc12",
        },
    )
    assert response.status_code == 422
    assert "at least 6 characters" in response.text


def test_register_password_too_long():
    """Passwords over bcrypt's 72-byte limit get a clean 400, not a crash."""
    long_password = "aB3" * 30  # 90 characters, > 72 bytes
    response = client.post(
        "/auth/register",
        json={
            "email": _unique_email(),
            "full_name": "Deepika",
            "password": long_password,
            "password_confirm": long_password,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Password is too long (maximum 72 bytes)."


def test_register_duplicate_email_rejected():
    email = _unique_email()
    first = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Deepika",
            "password": "Deepika123",
            "password_confirm": "Deepika123",
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Deepika Two",
            "password": "Deepika123",
            "password_confirm": "Deepika123",
        },
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Email already registered"
