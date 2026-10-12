from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum
from app.models.enums import ImportStatus, TransactionSource, TransactionType

Money = Numeric(18, 2)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[ImportStatus] = mapped_column(
        str_enum(ImportStatus, "import_status"), nullable=False
    )
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Row-level validation errors, capped in size by the import service.
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "rows_total >= 0 AND rows_inserted >= 0 AND rows_duplicate >= 0 AND rows_rejected >= 0",
            name="row_counts_non_negative",
        ),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # sha256 of external_id (API) or of the canonical row fields (CSV): makes imports idempotent.
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    external_id: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[TransactionSource] = mapped_column(
        str_enum(TransactionSource, "transaction_source"), nullable=False
    )
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="RESTRICT"), index=True
    )
    # PaySim "step": simulated hour since the start of the simulation (1 = first hour).
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    type: Mapped[TransactionType] = mapped_column(
        str_enum(TransactionType, "transaction_type"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    origin_account: Mapped[str] = mapped_column(String(64), nullable=False)
    dest_account: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_balance_before: Mapped[Decimal] = mapped_column(Money, nullable=False)
    origin_balance_after: Mapped[Decimal] = mapped_column(Money, nullable=False)
    dest_balance_before: Mapped[Decimal] = mapped_column(Money, nullable=False)
    dest_balance_after: Mapped[Decimal] = mapped_column(Money, nullable=False)
    # Ground-truth label from synthetic data. Used only for evaluation, never shown as a verdict.
    label_is_fraud: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # History lookups for scoring: "earlier transactions from/to this account".
        Index("ix_transactions_origin_step", "origin_account", "step"),
        Index("ix_transactions_dest_step", "dest_account", "step"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("step >= 0", name="step_non_negative"),
        CheckConstraint(
            "origin_balance_before >= 0 AND origin_balance_after >= 0 "
            "AND dest_balance_before >= 0 AND dest_balance_after >= 0",
            name="balances_non_negative",
        ),
    )
