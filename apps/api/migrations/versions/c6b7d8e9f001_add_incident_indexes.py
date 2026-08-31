"""add incident lookup indexes

Revision ID: c6b7d8e9f001
Revises: 7f2b66a9c3e1
Create Date: 2026-08-31 06:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c6b7d8e9f001"
down_revision: Union[str, Sequence[str], None] = "7f2b66a9c3e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_incidents_merchant_dimension_status",
        "incidents",
        ["merchant_id", "dimension_key", "status"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_merchant_cooldown",
        "incidents",
        ["merchant_id", "cooldown_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_merchant_cooldown", table_name="incidents")
    op.drop_index("ix_incidents_merchant_dimension_status", table_name="incidents")
