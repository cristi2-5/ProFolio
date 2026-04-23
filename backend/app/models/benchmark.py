"""
BenchmarkScore ORM Model.

GDPR-compliant competitive benchmarking. Scores are calculated using
only anonymized, aggregated data from users who have opted in.
Snapshots seniority and niche at calculation time for historical accuracy.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BenchmarkScore(Base):
    """A user's competitive benchmark score for a specific job.

    Score (0-100) reflects CV strength relative to peers at the same
    seniority level and niche. Requires minimum 30 peers in the group
    before generating a comparative score (enforced at application layer).

    GDPR Compliance:
        - Only includes data from users with benchmark_opt_in=True
        - Uses aggregated, anonymized statistics (no PII in calculations)
        - User can opt-out at any time without losing platform access

    Attributes:
        id: UUID primary key.
        user_id: Foreign key to user.
        job_id: Foreign key to the job being benchmarked against.
        score: Competitiveness score (0-100).
        peer_group_size: Number of peers in the comparison group.
        seniority_level: Snapshot of user's level at calculation time.
        niche: Snapshot of user's niche at calculation time.
        missing_skills: JSONB with top 3 skill gaps and justifications.
        recommended_keywords: JSONB with ATS-friendly keyword suggestions.
        calculated_at: When the benchmark was computed.
    """

    __tablename__ = "benchmark_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scraped_jobs.id", ondelete="SET NULL"),
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    peer_group_size: Mapped[int | None] = mapped_column(Integer)
    seniority_level: Mapped[str | None] = mapped_column(String(20))
    niche: Mapped[str | None] = mapped_column(String(100))
    missing_skills: Mapped[dict | None] = mapped_column(JSONB)
    recommended_keywords: Mapped[dict | None] = mapped_column(JSONB)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="benchmark_scores")  # noqa: F821
    job: Mapped["ScrapedJob | None"] = relationship(  # noqa: F821
        back_populates="benchmark_scores"
    )

    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_benchmark_score_range"),
    )

    def __repr__(self) -> str:
        """Return string representation of BenchmarkScore."""
        return (
            f"<BenchmarkScore(user_id={self.user_id}, "
            f"score={self.score}, level='{self.seniority_level}')>"
        )

    # ------------------------------------------------------------------
    # Typed accessors for the JSONB payloads the service writes.
    # These are the single source of truth for the payload shape so the
    # router doesn't need to peek inside the JSONB.
    # ------------------------------------------------------------------

    def skill_gap_items(self) -> list[dict]:
        """Unpack the ``missing_skills`` payload written by BenchmarkService."""
        raw = self.missing_skills
        if isinstance(raw, dict):
            items = raw.get("items")
            return items if isinstance(items, list) else []
        if isinstance(raw, list):
            return raw
        return []

    def keyword_payload(self) -> dict:
        """Unpack the ``recommended_keywords`` payload. Keys:
        ``items``, ``matched``, ``user_match_score``, ``peer_mean_match_score``.
        """
        raw = self.recommended_keywords
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            return {"items": raw}
        return {}
