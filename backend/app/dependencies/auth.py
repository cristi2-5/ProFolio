"""
JWT Authentication Dependency.

Provides FastAPI dependency injection for protected routes requiring
authentication. Validates JWT tokens and retrieves authenticated users.
"""

from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User

settings = get_settings()
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate JWT token, return authenticated user.

    This dependency is used to protect routes that require authentication.
    It validates the JWT token from the Authorization header and retrieves
    the corresponding user from the database.

    Args:
        credentials: HTTP Bearer token from Authorization header.
        db: Database session for user lookup.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: 401 if token is invalid, expired, or user not found.

    Usage:
        @router.get("/protected")
        async def protected_route(
            current_user: Annotated[User, Depends(get_current_user)]
        ):
            return {"user_id": current_user.id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        # Decode JWT token
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )

        # Extract user ID from token payload
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception

        # Parse UUID
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise credentials_exception

        # Verify token expiration
        exp: int | None = payload.get("exp")
        if exp is None:
            raise credentials_exception

        if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except JWTError:
        raise credentials_exception

    # Retrieve user from database
    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Optional: Additional validation for active users.

    This dependency chains on top of get_current_user to add extra
    validation (e.g., checking if user account is disabled/suspended).
    Currently returns the user as-is, but can be extended with
    account status checks in the future.

    Args:
        current_user: User from get_current_user dependency.

    Returns:
        User: The authenticated active user.

    Raises:
        HTTPException: 403 if user account is inactive (future enhancement).
    """
    # Future: Add is_active field to User model and check here
    # if not current_user.is_active:
    #     raise HTTPException(status_code=403, detail="Inactive user")

    return current_user
