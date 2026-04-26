"""
Feedback ORM Model.

Collects qualitative + quantitative feedback on AI-generated content so
the team can iterate on prompt quality. A single ``content_type`` column
discriminates between optimized CVs, cover letters, interview prep, and
benchmarks, keeping schema changes minimal if we add more AI outputs.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContentType(str, enum.Enum):
    """Discriminator for the AI surface a piece of feedback targets.

    Kept as a `str` Enum so values serialise cleanly in JSON and land
    directly into the DB ``content_type`` column without a custom type
    adapter. The DB-level CHECK constraint uses the same literals.
    """

    OPTIMIZED_CV = "optimized_cv"
    COVER_LETTER = "cover_letter"
    INTERVIEW_PREP = "interview_prep"
    BENCHMARK = "benchmark"
    OTHER = "other"


_CONTENT_TYPE_SQL_LIST = ", ".join(f"'{ct.value}'" for ct in ContentType)


class Feedback(Base):
    """User feedback on a piece of AI-generated content.

    Attributes:
        id: UUID primary key.
        user_id: Author of the feedback (cascades on user delete).
        content_type: One of the accepted AI surfaces (see CHECK constraint).
        content_id: Free-form identifier for the thing being rated
            (e.g. UserJob UUID, Benchmark UUID). Stored as TEXT so we're
            not locked into the shape of any one table.
        rating: 1-5 stars.
        comment: Optional free-text feedback (nullable, capped at ~2KB).
        created_at: When the feedback was submitted.
    """

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        CheckConstraint(
            f"content_type IN ({_CONTENT_TYPE_SQL_LIST})",
            name="ck_feedback_content_type",
        ),
        Index("ix_feedback_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Feedback(user_id={self.user_id}, "
            f"type='{self.content_type}', rating={self.rating})>"
        )
