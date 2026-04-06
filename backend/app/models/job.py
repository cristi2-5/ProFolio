"""
ScrapedJob & UserJob ORM Models.

ScrapedJob: Jobs discovered by the Job Scanner agent (source-agnostic).
UserJob: Many-to-many relationship tracking per-user job status,
         match scores, optimized CVs, and interview prep materials.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScrapedJob(Base):
    """A job listing discovered by the Job Scanner agent.

    Uses description_hash (SHA-256 of first 200 chars) for cross-platform
    deduplication — the same role posted on LinkedIn and Indeed will be
    caught by matching company_name + job_title + description_hash.

    Attributes:
        id: UUID primary key.
        external_url: Original job posting URL (unique).
        company_name: Hiring company name.
        job_title: Role title.
        description: Full job description text.
        description_hash: SHA-256 of first 200 chars for dedup.
        location: Job location string.
        source_platform: Where the job was found (e.g., "adzuna").
        scraped_at: When the job was discovered.
    """

    __tablename__ = "scraped_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_url: Mapped[str | None] = mapped_column(String(500), unique=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    description_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    source_platform: Mapped[str | None] = mapped_column(String(100))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user_jobs: Mapped[list["UserJob"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    benchmark_scores: Mapped[list["BenchmarkScore"]] = relationship(  # noqa: F821
        back_populates="job"
    )

    __table_args__ = (
        # Composite index for cross-platform deduplication
        UniqueConstraint(
            "company_name",
            "job_title",
            "description_hash",
            name="uq_job_dedup",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of ScrapedJob."""
        return (
            f"<ScrapedJob(id={self.id}, "
            f"title='{self.job_title}' @ '{self.company_name}')>"
        )


class UserJob(Base):
    """Association between a user and a scraped job.

    Tracks match score, application status, and stores AI-generated
    content (optimized CV, cover letter, interview prep) per job.

    Attributes:
        id: UUID primary key.
        user_id: Foreign key to user.
        job_id: Foreign key to scraped job.
        match_score: AI-calculated compatibility percentage (0-100).
        status: Job pipeline status (new/applied/saved/hidden/duplicate).
        optimized_cv: JSONB with LLM-rewritten CV bullet points.
        cover_letter: Generated cover letter text.
        interview_prep: JSONB with interview questions + cheat sheet.
        created_at: When the job was matched to the user.
        updated_at: Last status change.
    """

    __tablename__ = "user_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scraped_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(20), default="new")
    optimized_cv: Mapped[dict | None] = mapped_column(JSONB)
    cover_letter: Mapped[str | None] = mapped_column(Text)
    interview_prep: Mapped[dict | None] = mapped_column(JSONB)
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="user_jobs")  # noqa: F821
    job: Mapped["ScrapedJob"] = relationship(back_populates="user_jobs")

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="ck_userjob_match_score"),
        CheckConstraint(
            "status IN ('new', 'applied', 'saved', 'hidden', 'duplicate')",
            name="ck_userjob_status",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of UserJob."""
        return (
            f"<UserJob(user_id={self.user_id}, "
            f"job_id={self.job_id}, status='{self.status}')>"
        )
