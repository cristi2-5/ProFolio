"""
User & JobPreference ORM Models.

Supports authentication (email/password with bcrypt hashing),
seniority-based benchmarking, and GDPR opt-in consent.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Registered platform user.

    Attributes:
        id: UUID primary key, auto-generated.
        email: Unique email address for login.
        password_hash: Bcrypt-hashed password (never stored in plaintext).
        full_name: User's display name.
        seniority_level: Self-reported level for benchmark grouping.
        niche: Technical domain (required for mid/senior benchmarking).
        benchmark_opt_in: GDPR consent flag for anonymous benchmarking.
        created_at: Account creation timestamp.
        updated_at: Last profile update timestamp.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    seniority_level: Mapped[str | None] = mapped_column(String(20))
    niche: Mapped[str | None] = mapped_column(String(100))
    benchmark_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    job_preference: Mapped["JobPreference | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    resumes: Mapped[list["ParsedResume"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    user_jobs: Mapped[list["UserJob"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    benchmark_scores: Mapped[list["BenchmarkScore"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "seniority_level IN ('intern', 'junior', 'mid', 'senior')",
            name="ck_user_seniority_level",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f"<User(id={self.id}, email='{self.email}')>"


class JobPreference(Base):
    """User's job search criteria for the Job Scanner agent.

    One preference set per user. Stores the desired role title,
    location type, and up to 5 search keywords.

    Attributes:
        id: UUID primary key.
        user_id: Foreign key to the owning user.
        desired_title: Target job title (e.g., 'Frontend Intern').
        location_type: remote, hybrid, or onsite.
        keywords: Array of 3-5 search keywords.
        created_at: Preference creation timestamp.
    """

    __tablename__ = "job_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    desired_title: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[str | None] = mapped_column(String(20))
    keywords: Mapped[list | None] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="job_preference")

    __table_args__ = (
        CheckConstraint(
            "location_type IN ('remote', 'hybrid', 'onsite')",
            name="ck_jobpref_location_type",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of JobPreference."""
        return f"<JobPreference(user_id={self.user_id}, title='{self.desired_title}')>"
