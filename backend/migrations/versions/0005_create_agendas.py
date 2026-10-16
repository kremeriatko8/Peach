"""Add agendas without modifying existing meeting or task rows."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agendas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "meeting_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("action_items", postgresql.JSONB(), nullable=False),
        sa.Column("language", sa.String(64), nullable=False),
        sa.Column("ai_suggestion", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("jsonb_typeof(items) = 'array'", name="ck_agendas_items"),
        sa.CheckConstraint("jsonb_typeof(action_items) = 'array'", name="ck_agendas_actions"),
        sa.CheckConstraint("length(trim(language)) > 0", name="ck_agendas_language"),
        sa.CheckConstraint(
            "ai_suggestion IS NULL OR jsonb_typeof(ai_suggestion) = 'object'",
            name="ck_agendas_suggestion",
        ),
    )


def downgrade():
    # Routine application rollback must preserve this schema and saved agendas.
    op.drop_table("agendas")
