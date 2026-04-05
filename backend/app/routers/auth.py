"""
Auth Router — Registration, Login, and Token endpoints.

Handles user authentication via email/password with JWT tokens.
OAuth (Google, LinkedIn) endpoints will be added in Phase 2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import datetime, timezone

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import LoginRequest, Token, UserCreate, UserResponse
from app.schemas.benchmark import BenchmarkOptInRequest, BenchmarkOptInResponse
from app.services.auth_service import AuthService
from app.utils.exceptions import DuplicateError, UnauthorizedError, raise_http_exception
from app.utils.security import sanitize_email, validate_password_strength

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account with validation.

    Validates password strength, email format, and checks for duplicates.
    Creates user with hashed password and returns public profile.

    Args:
        user_data: Registration payload with email, password, and profile info.
        db: Async database session (injected).

    Returns:
        UserResponse: The created user's public profile.

    Raises:
        HTTPException 400: If password requirements not met or email invalid.
        HTTPException 409: If email already exists.
        HTTPException 422: If required fields missing for seniority level.
    """
    try:
        # Validate and sanitize email
        sanitized_email = sanitize_email(user_data.email)

        # Validate password strength
        is_valid, password_errors = validate_password_strength(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password requirements not met: {', '.join(password_errors)}"
            )

        # Business rule: Mid/senior levels require niche specification
        if user_data.seniority_level in ["mid", "senior"] and not user_data.niche:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{user_data.seniority_level.title()} level requires specifying your technical niche."
            )

        # Update user_data with sanitized email
        user_data.email = sanitized_email

        # Create user via service layer
        user = await AuthService.register(db, user_data)
        await db.commit()

        return UserResponse.model_validate(user)

    except DuplicateError as e:
        raise_http_exception(e)
    except ValueError as e:
        # Email validation errors from sanitize_email()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT token",
)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate a user and return a JWT access token.

    Validates email format, authenticates credentials, and returns
    JWT token for subsequent API calls. Rate limiting recommended
    via @limiter.limit("5/minute") decorator.

    Args:
        credentials: Login payload with email and password.
        db: Async database session (injected).

    Returns:
        Token: JWT access token with "bearer" type for Authorization header.

    Raises:
        HTTPException 400: If email format is invalid.
        HTTPException 401: If credentials are invalid or user not found.
    """
    try:
        # Validate and sanitize email
        sanitized_email = sanitize_email(credentials.email)

        # Authenticate via service layer
        access_token = await AuthService.authenticate(db, sanitized_email, credentials.password)

        return Token(access_token=access_token, token_type="bearer")

    except UnauthorizedError as e:
        raise_http_exception(e)
    except ValueError as e:
        # Email validation errors from sanitize_email()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ================================================================
# User Profile & Account Management
# ================================================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Retrieve the authenticated user's profile information.

    Returns complete user profile including personal information,
    preferences, and account settings.

    Args:
        current_user: Authenticated user (injected).

    Returns:
        UserResponse: Complete user profile data.
    """
    return UserResponse.model_validate(current_user)


@router.patch(
    "/benchmark-opt-in",
    response_model=BenchmarkOptInResponse,
    summary="Update benchmark participation preferences",
)
async def update_benchmark_opt_in(
    opt_in_request: BenchmarkOptInRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BenchmarkOptInResponse:
    """Update user's benchmark participation consent (GDPR-compliant).

    Allows users to opt into or out of competitive benchmarking.
    When opted in, user's anonymized data will be included in
    peer group comparisons for benchmarking calculations.

    Args:
        opt_in_request: New opt-in preference.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        BenchmarkOptInResponse: Updated opt-in status with privacy notice.
    """
    try:
        # Update user's benchmark opt-in preference
        current_user.benchmark_opt_in = opt_in_request.benchmark_opt_in
        current_user.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(current_user)

        return BenchmarkOptInResponse(
            user_id=str(current_user.id),
            benchmark_opt_in=current_user.benchmark_opt_in,
            updated_at=current_user.updated_at,
            privacy_notice=(
                "Your data will only be used in anonymized aggregations for benchmarking. "
                "You can opt out at any time. No personal information is shared."
            ),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update benchmark preferences",
        )


@router.get(
    "/benchmark-opt-in",
    response_model=BenchmarkOptInResponse,
    summary="Get current benchmark participation status",
)
async def get_benchmark_opt_in_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> BenchmarkOptInResponse:
    """Retrieve user's current benchmark participation status.

    Shows whether the user has consented to participate in
    competitive benchmarking and related privacy information.

    Args:
        current_user: Authenticated user (injected).

    Returns:
        BenchmarkOptInResponse: Current opt-in status with privacy notice.
    """
    return BenchmarkOptInResponse(
        user_id=str(current_user.id),
        benchmark_opt_in=current_user.benchmark_opt_in,
        updated_at=current_user.updated_at,
        privacy_notice=(
            "Your data will only be used in anonymized aggregations for benchmarking. "
            "You can opt out at any time. No personal information is shared."
        ),
    )
