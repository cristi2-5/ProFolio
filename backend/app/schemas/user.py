"""
User Pydantic Schemas — Request/Response validation.

Separates input (Create/Update) from output (Response) schemas
to prevent leaking sensitive fields like password_hash.
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    """Schema for user registration requests.

    Attributes:
        email: Valid email address.
        password: Plain-text password (min 8 chars, hashed before storage).
        full_name: Optional display name.
        seniority_level: Optional seniority for benchmarking.
        niche: Optional technical domain (required for mid/senior).
    """

    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    seniority_level: Optional[str] = Field(None, pattern="^(intern|junior|mid|senior)$")
    niche: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        """Basic email validation that's more permissive than EmailStr."""
        if not isinstance(v, str):
            raise ValueError("Email must be a string")

        v = v.strip().lower()

        # Basic email pattern - allows .test, .local, etc for development
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")

        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        """Reject all-whitespace passwords and enforce bcrypt's 72-byte limit."""
        if not isinstance(v, str):
            raise ValueError("Password must be a string")
        if not v.strip():
            raise ValueError("Password must not be empty or whitespace only")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password too long: max 72 bytes when UTF-8 encoded")
        return v


class UserUpdate(BaseModel):
    """Schema for profile update requests.

    All fields optional — only provided fields are updated.
    """

    full_name: Optional[str] = None
    seniority_level: Optional[str] = Field(None, pattern="^(intern|junior|mid|senior)$")
    niche: Optional[str] = None
    benchmark_opt_in: Optional[bool] = None


class UserResponse(BaseModel):
    """Schema for user data in API responses.

    Never includes password_hash or other sensitive internal fields.
    """

    id: uuid.UUID
    email: str
    full_name: Optional[str]
    seniority_level: Optional[str]
    niche: Optional[str]
    benchmark_opt_in: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT token response schema.

    Attributes:
        access_token: The JWT string.
        token_type: Always "bearer".
    """

    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Schema for login requests.

    Attributes:
        email: User's registered email.
        password: Plain-text password for verification.
    """

    email: str = Field(..., description="User's registered email")
    password: str

    @field_validator("email")
    @classmethod
    def validate_login_email(cls, v):
        """Basic email validation for login."""
        if not isinstance(v, str):
            raise ValueError("Email must be a string")

        v = v.strip().lower()

        # Basic email pattern - allows .test, .local, etc for development
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")

        return v

    @field_validator("password")
    @classmethod
    def validate_login_password(cls, v):
        """Reject all-whitespace passwords."""
        if not isinstance(v, str):
            raise ValueError("Password must be a string")
        if not v.strip():
            raise ValueError("Password must not be empty or whitespace only")
        return v


class JobPreferenceCreate(BaseModel):
    """Schema for creating/updating job preferences.

    Attributes:
        desired_title: Target job title (e.g., 'Frontend Developer').
        location_type: Work location preference.
        keywords: Array of 3-5 search keywords.
    """

    desired_title: str = Field(..., min_length=2, max_length=255)
    location_type: str = Field(..., pattern="^(remote|hybrid|onsite)$")
    keywords: list[str] = Field(..., min_length=3, max_length=5)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v):
        """Validate keywords are non-empty and reasonable length."""
        if not v:
            raise ValueError("At least 3 keywords required")
        for keyword in v:
            if not keyword.strip():
                raise ValueError("Keywords cannot be empty")
            if len(keyword) > 50:
                raise ValueError("Keywords must be 50 characters or less")
        return [keyword.strip() for keyword in v]


class JobPreferenceResponse(BaseModel):
    """Schema for job preferences in API responses.

    Attributes:
        id: Preference UUID.
        user_id: Owner's user ID.
        desired_title: Target job title.
        location_type: Work location preference.
        keywords: Search keywords array.
        created_at: Creation timestamp.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    desired_title: str
    location_type: Optional[str]
    keywords: Optional[list[str]]
    created_at: datetime

    model_config = {"from_attributes": True}
