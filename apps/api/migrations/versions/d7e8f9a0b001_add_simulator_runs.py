"""add persisted simulator run lifecycle

Revision ID: d7e8f9a0b001
Revises: c6b7d8e9f001
Create Date: 2026-08-31 10:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7e8f9a0b001"
down_revision: Union[str, Sequence[str], None] = "c6b7d8e9f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulator_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=False),
        sa.Column("run_key", sa.String(length=255), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_safe", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "run_key", name="uq_simulator_run_key"),
    )
    op.create_index(
        "ix_simulator_runs_merchant_status",
        "simulator_runs",
        ["merchant_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_simulator_runs_merchant_status", table_name="simulator_runs")
    op.drop_table("simulator_runs")
