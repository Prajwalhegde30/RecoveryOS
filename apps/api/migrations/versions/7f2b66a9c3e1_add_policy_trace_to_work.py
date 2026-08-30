"""add policy trace to actions and jobs

Revision ID: 7f2b66a9c3e1
Revises: 43b1e3d41169
Create Date: 2026-08-31 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f2b66a9c3e1"
down_revision: Union[str, Sequence[str], None] = "43b1e3d41169"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recovery_actions",
        sa.Column("policy_version_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_recovery_actions_policy_version",
        "recovery_actions",
        "policy_versions",
        ["policy_version_id"],
        ["id"],
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("policy_decision_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("policy_version_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_scheduled_jobs_policy_decision",
        "scheduled_jobs",
        "policy_decisions",
        ["policy_decision_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_scheduled_jobs_policy_version",
        "scheduled_jobs",
        "policy_versions",
        ["policy_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_scheduled_jobs_policy_version", "scheduled_jobs", type_="foreignkey")
    op.drop_constraint("fk_scheduled_jobs_policy_decision", "scheduled_jobs", type_="foreignkey")
    op.drop_column("scheduled_jobs", "policy_version_id")
    op.drop_column("scheduled_jobs", "policy_decision_id")
    op.drop_constraint(
        "fk_recovery_actions_policy_version", "recovery_actions", type_="foreignkey"
    )
    op.drop_column("recovery_actions", "policy_version_id")
