"""
Auth Service — Business logic for user registration and authentication.

Encapsulates password hashing, duplicate checking, and JWT issuance.
Keeps router layer thin (controller pattern).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
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

    @staticmethod
    async def update_user(
        db: AsyncSession,
        current_user: User,
        payload: UserUpdate,
    ) -> User:
        """Apply a partial update to the user's profile.

        Only fields explicitly provided on payload (non-unset) are touched.
        Email changes re-check uniqueness across other users. If the
        resulting seniority is mid/senior, niche must be set on either the
        payload or the existing user (cross-field validation).

        Args:
            db: Async database session.
            current_user: The authenticated user being updated.
            payload: Validated update fields.

        Returns:
            User: The refreshed user instance.

        Raises:
            DuplicateError: If email change collides with another user.
            ValueError: If mid/senior level resolves with no niche.
        """
        update_dict = payload.model_dump(exclude_unset=True)

        # Email change — recheck uniqueness against other users.
        if "email" in update_dict and update_dict["email"] != current_user.email:
            new_email = update_dict["email"]
            stmt = select(User).where(
                User.email == new_email, User.id != current_user.id
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                raise DuplicateError("User", "email")

        # Cross-field validation: mid/senior require niche.
        new_seniority = update_dict.get(
            "seniority_level", current_user.seniority_level
        )
        new_niche = update_dict.get("niche", current_user.niche)
        if new_seniority in ("mid", "senior") and not new_niche:
            raise ValueError(
                f"{new_seniority.title()} level requires specifying your technical niche."
            )

        for field, value in update_dict.items():
            setattr(current_user, field, value)

        await db.commit()
        await db.refresh(current_user)
        return current_user
