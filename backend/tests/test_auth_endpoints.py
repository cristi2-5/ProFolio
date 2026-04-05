"""
Authentication Endpoints Tests.

Tests user registration and login endpoints with comprehensive
validation scenarios, error handling, and JWT token verification.
"""

from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.utils.security import verify_password

settings = get_settings()


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def valid_registration_data() -> dict:
    """Sample valid user registration data."""
    return {
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "full_name": "John Doe",
        "seniority_level": "mid",
        "niche": "Backend Engineering"
    }


@pytest.fixture
def minimal_registration_data() -> dict:
    """Minimal valid registration (required fields only)."""
    return {
        "email": "minimal@example.com",
        "password": "Password123!"
    }


@pytest.fixture
async def existing_user(test_session: AsyncSession) -> User:
    """Create an existing user for duplicate/login tests."""
    from app.utils.security import hash_password

    user = User(
        email="existing@example.com",
        password_hash=hash_password("ExistingPassword123!"),
        full_name="Existing User",
        seniority_level="senior",
        niche="Full Stack Development",
        benchmark_opt_in=False
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


# =====================================================================
# Registration Endpoint Tests
# =====================================================================


class TestUserRegistration:
    """Test /api/auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_valid_user(
        self, test_client: TestClient, test_session: AsyncSession, valid_registration_data: dict
    ):
        """Valid registration should create user and return profile."""
        response = test_client.post("/api/auth/register", json=valid_registration_data)

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert data["email"] == valid_registration_data["email"].lower()
        assert data["full_name"] == valid_registration_data["full_name"]
        assert data["seniority_level"] == valid_registration_data["seniority_level"]
        assert data["niche"] == valid_registration_data["niche"]
        assert data["benchmark_opt_in"] is False  # Default value
        assert "created_at" in data
        assert "updated_at" in data
        assert "password" not in data  # Sensitive data excluded

        # Verify user was actually created in database
        result = await test_session.execute(
            select(User).where(User.email == valid_registration_data["email"].lower())
        )
        user = result.scalar_one()
        assert user is not None
        assert user.full_name == valid_registration_data["full_name"]
        assert verify_password(valid_registration_data["password"], user.password_hash)

    @pytest.mark.asyncio
    async def test_register_minimal_data(
        self, test_client: TestClient, test_session: AsyncSession, minimal_registration_data: dict
    ):
        """Registration with minimal data should succeed."""
        response = test_client.post("/api/auth/register", json=minimal_registration_data)

        assert response.status_code == 201
        data = response.json()

        assert data["email"] == minimal_registration_data["email"].lower()
        assert data["full_name"] is None
        assert data["seniority_level"] is None
        assert data["niche"] is None

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, test_client: TestClient, existing_user: User, valid_registration_data: dict
    ):
        """Duplicate email should return 409 Conflict."""
        # Try to register with same email as existing user
        valid_registration_data["email"] = existing_user.email

        response = test_client.post("/api/auth/register", json=valid_registration_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_email_format(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Invalid email format should return 400."""
        valid_registration_data["email"] = "not-an-email"

        response = test_client.post("/api/auth/register", json=valid_registration_data)

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_register_weak_password(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Weak password should return 400 with specific errors."""
        test_cases = [
            ("short", "Password requirements not met"),
            ("nouppercase123!", "uppercase letter"),
            ("NOLOWERCASE123!", "lowercase letter"),
            ("NoNumbers!", "number"),
            ("NoSpecialChars123", "special character"),
            ("Password123123123", "weak patterns")  # Repeated "123" pattern
        ]

        for password, expected_error in test_cases:
            valid_registration_data["password"] = password
            response = test_client.post("/api/auth/register", json=valid_registration_data)

            assert response.status_code == 400
            assert expected_error in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_mid_level_without_niche(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Mid-level without niche should return 422."""
        valid_registration_data["seniority_level"] = "mid"
        valid_registration_data["niche"] = None

        response = test_client.post("/api/auth/register", json=valid_registration_data)

        assert response.status_code == 422
        assert "Mid level requires specifying" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_senior_level_without_niche(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Senior level without niche should return 422."""
        valid_registration_data["seniority_level"] = "senior"
        valid_registration_data["niche"] = None

        response = test_client.post("/api/auth/register", json=valid_registration_data)

        assert response.status_code == 422
        assert "Senior level requires specifying" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_junior_level_without_niche(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Junior/intern levels don't require niche."""
        test_cases = ["junior", "intern"]

        for seniority in test_cases:
            valid_registration_data["seniority_level"] = seniority
            valid_registration_data["niche"] = None
            valid_registration_data["email"] = f"{seniority}@example.com"

            response = test_client.post("/api/auth/register", json=valid_registration_data)
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_register_email_case_insensitive(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Email should be normalized to lowercase."""
        valid_registration_data["email"] = "Test@EXAMPLE.COM"

        response = test_client.post("/api/auth/register", json=valid_registration_data)

        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"


# =====================================================================
# Login Endpoint Tests
# =====================================================================


class TestUserLogin:
    """Test /api/auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_valid_credentials(
        self, test_client: TestClient, existing_user: User
    ):
        """Valid credentials should return JWT token."""
        login_data = {
            "email": existing_user.email,
            "password": "ExistingPassword123!"
        }

        response = test_client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()

        # Verify token structure
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify JWT token is valid and contains user ID
        token = data["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == str(existing_user.id)
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, test_client: TestClient, existing_user: User
    ):
        """Wrong password should return 401."""
        login_data = {
            "email": existing_user.email,
            "password": "WrongPassword123!"
        }

        response = test_client.post("/api/auth/login", json=login_data)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(
        self, test_client: TestClient
    ):
        """Nonexistent email should return 401."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "SomePassword123!"
        }

        response = test_client.post("/api/auth/login", json=login_data)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_invalid_email_format(
        self, test_client: TestClient
    ):
        """Invalid email format should return 400."""
        login_data = {
            "email": "not-an-email",
            "password": "SomePassword123!"
        }

        response = test_client.post("/api/auth/login", json=login_data)

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_login_email_case_insensitive(
        self, test_client: TestClient, existing_user: User
    ):
        """Login should work with case-insensitive email."""
        login_data = {
            "email": existing_user.email.upper(),
            "password": "ExistingPassword123!"
        }

        response = test_client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_login_empty_fields(
        self, test_client: TestClient
    ):
        """Empty email/password should return validation errors."""
        test_cases = [
            {"email": "", "password": "Password123!"},
            {"email": "test@example.com", "password": ""},
            {"email": "", "password": ""}
        ]

        for login_data in test_cases:
            response = test_client.post("/api/auth/login", json=login_data)
            assert response.status_code == 422


# =====================================================================
# Integration Tests
# =====================================================================


class TestAuthFlow:
    """Test complete registration → login → authenticated request flow."""

    @pytest.mark.asyncio
    async def test_complete_auth_flow(
        self, test_client: TestClient, valid_registration_data: dict
    ):
        """Test register → login → authenticated API call flow."""
        # Step 1: Register new user
        register_response = test_client.post("/api/auth/register", json=valid_registration_data)
        assert register_response.status_code == 201
        user_data = register_response.json()

        # Step 2: Login with the same credentials
        login_data = {
            "email": valid_registration_data["email"],
            "password": valid_registration_data["password"]
        }
        login_response = test_client.post("/api/auth/login", json=login_data)
        assert login_response.status_code == 200

        token_data = login_response.json()
        access_token = token_data["access_token"]

        # Step 3: Verify JWT token contains correct user ID
        payload = jwt.decode(access_token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == user_data["id"]

        # Note: Protected endpoint test would go here when middleware is integrated
        # headers = {"Authorization": f"Bearer {access_token}"}
        # protected_response = test_client.get("/api/protected", headers=headers)
        # assert protected_response.status_code == 200