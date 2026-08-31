"""add persisted worker heartbeat registry

Revision ID: e1f0a1b2c003
Revises: d7e8f9a0b001
"""

import sqlalchemy as sa
from alembic import op

revision = "e1f0a1b2c003"
down_revision = "d7e8f9a0b001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("detail_safe", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "worker_id", name="uq_worker_heartbeat_identity"),
    )
    op.create_index(
        "ix_worker_heartbeats_merchant_seen",
        "worker_heartbeats",
        ["merchant_id", "last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_merchant_seen", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
