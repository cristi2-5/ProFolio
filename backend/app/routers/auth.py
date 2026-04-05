"""
Auth Router — Registration, Login, and Token endpoints.

Handles user authentication via email/password with JWT tokens.
OAuth (Google, LinkedIn) endpoints will be added in Phase 2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import LoginRequest, Token, UserCreate, UserResponse
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

    Args:
        credentials: Login payload with email and password.
        db: Async database session (injected).

    Returns:
        Token: JWT access token for subsequent API calls.

    Raises:
        HTTPException 401: If credentials are invalid.
    """
    # TODO: Implement via AuthService in Phase 2
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Login endpoint — implementation in Phase 2.",
    )
