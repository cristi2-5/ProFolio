"""Add applied_at column to user_jobs.

Revision ID: 005
Revises: 004
Create Date: 2026-04-06

Adds a nullable TIMESTAMPTZ column `applied_at` to `user_jobs`.
This column is set when a user marks a job as applied, enabling the
Application History tab to display when the application was submitted.

Non-breaking, additive migration — all existing rows default to NULL.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add applied_at column to user_jobs table."""
    op.add_column(
        "user_jobs",
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove applied_at column from user_jobs table."""
    op.drop_column("user_jobs", "applied_at")
