"""
Auth Service — Business logic for user registration and authentication.

Encapsulates password hashing, duplicate checking, and JWT issuance.
Keeps router layer thin (controller pattern).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.exceptions import DuplicateError, UnauthorizedError
from app.utils.security import create_access_token, hash_password, verify_password


class AuthService:
    """Handles user authentication business logic.

    Methods:
        register: Create a new user with hashed password.
        authenticate: Verify credentials and return JWT.
    """

    @staticmethod
    async def register(db: AsyncSession, user_data: UserCreate) -> User:
        """Register a new user.

        Args:
            db: Async database session.
            user_data: Validated registration data.

        Returns:
            User: The newly created user ORM instance.

        Raises:
            DuplicateError: If email is already registered.
        """
        # Check for existing email
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise DuplicateError("User", "email")

        # Create user with hashed password
        user = User(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            full_name=user_data.full_name,
            seniority_level=user_data.seniority_level,
            niche=user_data.niche,
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> str:
        """Authenticate a user and return a JWT token.

        Args:
            db: Async database session.
            email: User's email address.
            password: Plain-text password to verify.

        Returns:
            str: Signed JWT access token.

        Raises:
            UnauthorizedError: If email not found or password incorrect.
        """
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.")

        return create_access_token(data={"sub": str(user.id)})
