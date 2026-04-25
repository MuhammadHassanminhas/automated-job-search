"""Add llm_matched_skills JSONB column to jobs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("llm_matched_skills", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "llm_matched_skills")
