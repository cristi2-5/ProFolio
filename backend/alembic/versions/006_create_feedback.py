"""create feedback table

Revision ID: 006
Revises: 005
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.models.feedback import ContentType


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.String(length=255), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        sa.CheckConstraint(
            "content_type IN ({})".format(
                ", ".join(f"'{ct.value}'" for ct in ContentType)
            ),
            name="ck_feedback_content_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feedback_user_id", "feedback", ["user_id"]
    )
    op.create_index(
        "ix_feedback_user_created", "feedback", ["user_id", "created_at"]
    )
    op.execute(
        """
        COMMENT ON TABLE feedback IS
        'Phase 7 beta-launch feedback on AI-generated content.
         content_type discriminates between cv/cover/interview/benchmark.'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_user_created", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")
