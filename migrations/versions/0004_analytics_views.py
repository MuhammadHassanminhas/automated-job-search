"""Add analytics views.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-26
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW v_response_rate_by_source AS
        SELECT j.source::text AS source,
               COUNT(oe.id) FILTER (WHERE oe.direction = 'OUT') AS sent_count,
               COUNT(oe.id) FILTER (WHERE oe.direction = 'IN')  AS responded_count,
               ROUND(
                   COUNT(oe.id) FILTER (WHERE oe.direction = 'IN')::numeric /
                   NULLIF(COUNT(oe.id) FILTER (WHERE oe.direction = 'OUT'), 0),
               4) AS response_rate
        FROM jobs j
        JOIN applications a ON a.job_id = j.id
        JOIN outreach_events oe ON oe.application_id = a.id
        GROUP BY j.source
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW v_response_rate_by_prompt_version AS
        SELECT d.prompt_version,
               COUNT(oe.id) FILTER (WHERE oe.direction = 'OUT') AS sent_count,
               COUNT(oe.id) FILTER (WHERE oe.direction = 'IN')  AS responded_count,
               ROUND(
                   COUNT(oe.id) FILTER (WHERE oe.direction = 'IN')::numeric /
                   NULLIF(COUNT(oe.id) FILTER (WHERE oe.direction = 'OUT'), 0),
               4) AS response_rate
        FROM drafts d
        JOIN applications a ON a.id = d.application_id
        JOIN outreach_events oe ON oe.application_id = a.id
        GROUP BY d.prompt_version
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_response_rate_by_prompt_version")
    op.execute("DROP VIEW IF EXISTS v_response_rate_by_source")
