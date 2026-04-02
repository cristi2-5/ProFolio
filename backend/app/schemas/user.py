"""
User Pydantic Schemas — Request/Response validation.

Separates input (Create/Update) from output (Response) schemas
to prevent leaking sensitive fields like password_hash.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration requests.

    Attributes:
        email: Valid email address.
        password: Plain-text password (min 8 chars, hashed before storage).
        full_name: Optional display name.
        seniority_level: Optional seniority for benchmarking.
        niche: Optional technical domain (required for mid/senior).
    """

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    seniority_level: Optional[str] = Field(None, pattern="^(intern|junior|mid|senior)$")
    niche: Optional[str] = None


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

    email: EmailStr
    password: str
