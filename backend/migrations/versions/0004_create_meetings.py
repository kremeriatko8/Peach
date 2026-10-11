"""Add owner-scoped meetings without modifying tasks or their ownership.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_meetings_title"),
        sa.CheckConstraint("length(trim(owner_id)) > 0", name="ck_meetings_owner"),
        sa.CheckConstraint(
            "duration_minutes >= 1 AND duration_minutes <= 1440", name="ck_meetings_duration"
        ),
        sa.CheckConstraint(
            "participant_count >= 1 AND participant_count <= 10000", name="ck_meetings_participants"
        ),
    )
    op.create_index("ix_meetings_owner_id_starts_at", "meetings", ["owner_id", "starts_at"])


def downgrade() -> None:
    # Explicit downgrade deletes meetings. Routine rollback must retain this additive schema.
    op.drop_index("ix_meetings_owner_id_starts_at", table_name="meetings")
    op.drop_table("meetings")
