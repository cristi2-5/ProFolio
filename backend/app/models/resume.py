"""
ParsedResume ORM Model.

Stores CV data parsed by the CV Profiler agent. Uses PostgreSQL JSONB
for flexible structure since extracted fields vary by resume format.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParsedResume(Base):
    """A user's uploaded and parsed resume.

    The parsed_data JSONB field stores structured extraction output:
    {
        "skills": ["Python", "React", ...],
        "experience": [
            {"role": "...", "company": "...", "period": "...", "description": "..."}
        ],
        "education": [
            {"degree": "...", "institution": "...", "year": "..."}
        ],
        "technologies": ["Docker", "PostgreSQL", ...]
    }

    Attributes:
        id: UUID primary key.
        user_id: Foreign key to the owning user.
        original_filename: Name of the uploaded file.
        file_url: Path or URL to the stored file.
        parsed_data: JSONB with structured CV data.
        is_active: Whether this is the user's current active resume.
        created_at: Upload timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "parsed_resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str | None] = mapped_column(String(255))
    file_url: Mapped[str | None] = mapped_column(String(500))
    parsed_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="resumes")  # noqa: F821

    def __repr__(self) -> str:
        """Return string representation of ParsedResume."""
        return f"<ParsedResume(id={self.id}, " f"filename='{self.original_filename}')>"
