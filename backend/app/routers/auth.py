"""
Auth Router — Registration, Login, and Token endpoints.

Handles user authentication via email/password with JWT tokens.
OAuth (Google, LinkedIn) endpoints will be added in Phase 2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import LoginRequest, Token, UserCreate, UserResponse

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
    """Create a new user account.

    Args:
        user_data: Registration payload with email, password, and profile info.
        db: Async database session (injected).

    Returns:
        UserResponse: The created user's public profile.

    Raises:
        HTTPException 409: If email already exists.
    """
    # TODO: Implement via AuthService in Phase 2
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Registration endpoint — implementation in Phase 2.",
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
