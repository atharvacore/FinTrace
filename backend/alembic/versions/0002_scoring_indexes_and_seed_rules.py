"""scoring indexes and seed rules

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 07:22:40.134708
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Default monitoring rules. Thresholds are starting points for a PaySim-scale demo and are meant
# to be tuned by an admin (PATCH /api/v1/rules/{id}); every change is audited.
DEFAULT_RULES = [
    {
        "code": "LARGE_TRANSFER",
        "name": "Large transfer or cash-out",
        "description": "TRANSFER or CASH_OUT at or above a fixed amount.",
        "rule_type": "large_amount",
        "parameters": {"min_amount": "1000000", "types": ["TRANSFER", "CASH_OUT"]},
        "severity": "medium",
        "enabled": True,
    },
    {
        "code": "BALANCE_DRAIN",
        "name": "Account emptied",
        "description": "Outgoing TRANSFER or CASH_OUT that takes the whole available balance.",
        "rule_type": "balance_drain",
        "parameters": {"min_amount": "10000", "types": ["TRANSFER", "CASH_OUT"]},
        # Medium, not high: on PaySim 43% of legitimate transfers/cash-outs take the whole balance,
        # so as an alerting rule it buried analysts (32,978 alerts on 200,000 rows). It now adds
        # context to alerts instead of raising them on its own.
        "severity": "medium",
        "enabled": True,
    },
    {
        "code": "NEW_DESTINATION",
        "name": "High-value payment to a new destination",
        "description": "TRANSFER to a customer account never seen receiving money before.",
        "rule_type": "new_destination",
        "parameters": {"min_amount": "200000", "types": ["TRANSFER"]},
        "severity": "medium",
        "enabled": True,
    },
    {
        "code": "ORIGIN_VELOCITY",
        "name": "Many transactions from one account",
        "description": "More than max_count transactions from the same account within the window.",
        "rule_type": "origin_velocity",
        "parameters": {"window_hours": 24, "max_count": 5},
        "severity": "medium",
        "enabled": True,
    },
]


def upgrade() -> None:
    op.add_column(
        "model_versions",
        sa.Column(
            "is_synthetic_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.alter_column(
        "risk_assessments", "model_version_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.drop_index(op.f("ix_risk_assessments_model_version_id"), table_name="risk_assessments")
    op.create_index(
        "ix_risk_assessments_model_transaction",
        "risk_assessments",
        ["model_version_id", "transaction_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_transactions_dest_account"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_origin_account"), table_name="transactions")
    op.create_index(
        "ix_transactions_dest_step", "transactions", ["dest_account", "step"], unique=False
    )
    op.create_index(
        "ix_transactions_origin_step", "transactions", ["origin_account", "step"], unique=False
    )

    rules = sa.table(
        "monitoring_rules",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("rule_type", sa.String),
        sa.column("parameters", postgresql.JSONB),
        sa.column("severity", sa.String),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(rules, DEFAULT_RULES)


def downgrade() -> None:
    codes = ", ".join(f"'{r['code']}'" for r in DEFAULT_RULES)
    op.execute(f"DELETE FROM monitoring_rules WHERE code IN ({codes})")  # noqa: S608
    op.drop_index("ix_transactions_origin_step", table_name="transactions")
    op.drop_index("ix_transactions_dest_step", table_name="transactions")
    op.create_index(
        op.f("ix_transactions_origin_account"), "transactions", ["origin_account"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_dest_account"), "transactions", ["dest_account"], unique=False
    )
    op.drop_index("ix_risk_assessments_model_transaction", table_name="risk_assessments")
    op.create_index(
        op.f("ix_risk_assessments_model_version_id"),
        "risk_assessments",
        ["model_version_id"],
        unique=False,
    )
    op.alter_column(
        "risk_assessments", "model_version_id", existing_type=sa.INTEGER(), nullable=True
    )
    op.drop_column("model_versions", "is_synthetic_demo")
