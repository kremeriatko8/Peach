"""Add nullable ownership; preserve legacy rows without assigning a user.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("owner_id", sa.String(128), nullable=True))
    op.create_index("ix_items_owner_id_created_at", "items", ["owner_id", "created_at"])


def downgrade() -> None:
    # Explicit downgrade loses ownership information; never use as routine rollback.
    op.drop_index("ix_items_owner_id_created_at", table_name="items")
    op.drop_column("items", "owner_id")
