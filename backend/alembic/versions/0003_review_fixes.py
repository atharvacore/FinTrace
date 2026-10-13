"""one open alert per transaction, step starts at 1

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12 14:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPEN_STATUSES = "status IN ('open', 'in_review', 'escalated')"


def upgrade() -> None:
    # A transaction may have many alerts over time, but at most one that is still being worked.
    op.create_index(
        "uq_alerts_one_open_per_transaction",
        "alerts",
        ["transaction_id"],
        unique=True,
        postgresql_where=sa.text(OPEN_STATUSES),
    )
    # PaySim steps start at 1 (step 1 = first simulated hour); step 0 had no meaning.
    op.drop_constraint(op.f("ck_transactions_step_non_negative"), "transactions", type_="check")
    op.create_check_constraint(op.f("ck_transactions_step_positive"), "transactions", "step >= 1")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_transactions_step_positive"), "transactions", type_="check")
    op.create_check_constraint(
        op.f("ck_transactions_step_non_negative"), "transactions", "step >= 0"
    )
    op.drop_index("uq_alerts_one_open_per_transaction", table_name="alerts")
