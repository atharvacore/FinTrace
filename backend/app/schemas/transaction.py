from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import (
    AlertStatus,
    ImportStatus,
    RiskLevel,
    TransactionSource,
    TransactionType,
)
from app.schemas.common import ORMModel

AccountId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")]
Amount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
Balance = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class TransactionIn(BaseModel):
    """One transaction as accepted by the CSV importer and the ingestion API."""

    external_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")] | None = None
    step: int = Field(ge=1, le=1_000_000, description="Simulated hour (PaySim 'step')")
    type: TransactionType
    amount: Amount
    origin_account: AccountId
    dest_account: AccountId
    origin_balance_before: Balance
    origin_balance_after: Balance
    dest_balance_before: Balance
    dest_balance_after: Balance
    label_is_fraud: bool | None = Field(
        default=None, description="Synthetic ground-truth label, for evaluation only"
    )


class ApiTransactionIn(TransactionIn):
    # The API requires a client-chosen ID so retries are idempotent.
    external_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]


class TransactionBatchIn(BaseModel):
    transactions: list[ApiTransactionIn] = Field(min_length=1, max_length=1000)


class IngestItemResult(BaseModel):
    external_id: str
    id: int
    status: Literal["created", "duplicate"]


class IngestResult(BaseModel):
    inserted: int
    duplicates: int
    items: list[IngestItemResult]


class TransactionRead(ORMModel):
    id: int
    external_id: str | None
    source: TransactionSource
    import_batch_id: int | None
    step: int
    occurred_at: datetime
    type: TransactionType
    amount: Decimal
    origin_account: str
    dest_account: str
    origin_balance_before: Decimal
    origin_balance_after: Decimal
    dest_balance_before: Decimal
    dest_balance_after: Decimal
    created_at: datetime


class TransactionListItem(TransactionRead):
    risk_score: Decimal | None = Field(description="Latest assessment's score, if scored")
    risk_level: RiskLevel | None
    has_open_alert: bool


class AlertSummary(ORMModel):
    id: int
    status: AlertStatus
    priority: RiskLevel
    assignee_id: int | None
    created_at: datetime


class TransactionDetail(TransactionRead):
    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    synthetic_label_is_fraud: bool | None = Field(
        validation_alias="label_is_fraud",
        description="Ground-truth label from the synthetic dataset. Shown for evaluation; "
        "it is not an investigation outcome.",
    )


class ImportRowError(BaseModel):
    row: int = Field(description="1-based line number in the file, header is line 1")
    errors: list[str]


class ImportBatchRead(ORMModel):
    id: int
    filename: str
    file_sha256: str
    uploaded_by_id: int | None
    status: ImportStatus
    rows_total: int
    rows_inserted: int
    rows_duplicate: int
    rows_rejected: int
    errors: list[ImportRowError]
    created_at: datetime

    @computed_field
    @property
    def errors_truncated(self) -> bool:
        """True when more rows were rejected than are listed in `errors`."""
        return self.rows_rejected > len(self.errors)
