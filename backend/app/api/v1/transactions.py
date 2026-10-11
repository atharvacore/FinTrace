from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import Select, func, or_, select

from app.api.deps import AnalystUser, DbSession, SeniorUser
from app.core.errors import AppError, not_found
from app.models import Transaction
from app.models.enums import TransactionSource, TransactionType
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.transaction import (
    IngestItemResult,
    IngestResult,
    TransactionBatchIn,
    TransactionDetail,
    TransactionRead,
)
from app.services.audit import record_audit
from app.services.ingestion import ingest_api_transactions

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


class TransactionSort(StrEnum):
    NEWEST = "-occurred_at"
    OLDEST = "occurred_at"
    AMOUNT_DESC = "-amount"
    AMOUNT_ASC = "amount"


_ORDER = {
    TransactionSort.NEWEST: (Transaction.occurred_at.desc(), Transaction.id.desc()),
    TransactionSort.OLDEST: (Transaction.occurred_at.asc(), Transaction.id.asc()),
    TransactionSort.AMOUNT_DESC: (Transaction.amount.desc(), Transaction.id.desc()),
    TransactionSort.AMOUNT_ASC: (Transaction.amount.asc(), Transaction.id.asc()),
}


class TransactionFilters:
    """Query-string filters for the transaction search."""

    def __init__(
        self,
        q: Annotated[
            str | None,
            Query(max_length=100, description="Account ID or external ID (prefix match)"),
        ] = None,
        type: Annotated[list[TransactionType] | None, Query()] = None,  # noqa: A002
        account: Annotated[
            str | None, Query(max_length=64, description="Exact origin or destination account")
        ] = None,
        min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
        max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
        occurred_from: Annotated[datetime | None, Query(alias="from")] = None,
        occurred_to: Annotated[datetime | None, Query(alias="to")] = None,
        source: TransactionSource | None = None,
        import_batch_id: int | None = None,
        sort: TransactionSort = TransactionSort.NEWEST,
    ) -> None:
        if min_amount is not None and max_amount is not None and min_amount > max_amount:
            raise AppError(422, "VALIDATION_ERROR", "min_amount must not exceed max_amount")
        if occurred_from and occurred_to and occurred_from > occurred_to:
            raise AppError(422, "VALIDATION_ERROR", "'from' must not be after 'to'")
        self.q = q.strip() if q else None
        self.types = type
        self.account = account
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.occurred_from = occurred_from
        self.occurred_to = occurred_to
        self.source = source
        self.import_batch_id = import_batch_id
        self.sort = sort

    def apply(self, stmt: Select) -> Select:
        if self.q:
            pattern = self.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            stmt = stmt.where(
                or_(
                    Transaction.origin_account.like(pattern),
                    Transaction.dest_account.like(pattern),
                    Transaction.external_id.like(pattern),
                )
            )
        if self.types:
            stmt = stmt.where(Transaction.type.in_(self.types))
        if self.account:
            stmt = stmt.where(
                or_(
                    Transaction.origin_account == self.account,
                    Transaction.dest_account == self.account,
                )
            )
        if self.min_amount is not None:
            stmt = stmt.where(Transaction.amount >= self.min_amount)
        if self.max_amount is not None:
            stmt = stmt.where(Transaction.amount <= self.max_amount)
        if self.occurred_from:
            stmt = stmt.where(Transaction.occurred_at >= self.occurred_from)
        if self.occurred_to:
            stmt = stmt.where(Transaction.occurred_at <= self.occurred_to)
        if self.source:
            stmt = stmt.where(Transaction.source == self.source)
        if self.import_batch_id is not None:
            stmt = stmt.where(Transaction.import_batch_id == self.import_batch_id)
        return stmt


@router.post(
    "",
    response_model=IngestResult,
    summary="Ingest 1 to 1000 transactions (idempotent by external_id)",
    description=(
        "Each transaction needs a unique `external_id`. Sending the same ID again returns "
        "`duplicate` with the existing transaction ID instead of creating a copy. "
        "Responds 201 when anything new was created, otherwise 200."
    ),
    responses={201: {"model": IngestResult}, 422: {"model": ErrorResponse}},
)
def ingest_transactions(
    body: TransactionBatchIn,
    user: SeniorUser,
    db: DbSession,
    request: Request,
    response: Response,
) -> IngestResult:
    inserted, results = ingest_api_transactions(db, body.transactions)
    record_audit(
        db,
        actor=user,
        action="transactions.ingested",
        entity_type="transaction_batch",
        entity_id=getattr(request.state, "request_id", "-"),
        after={"received": len(results), "inserted": inserted},
        request=request,
    )
    db.commit()
    response.status_code = status.HTTP_201_CREATED if inserted else status.HTTP_200_OK
    return IngestResult(
        inserted=inserted,
        duplicates=len(results) - inserted,
        items=[
            IngestItemResult(external_id=ext, id=tx_id, status="created" if new else "duplicate")
            for ext, tx_id, new in results
        ],
    )


@router.get("", response_model=Page[TransactionRead], summary="Search transactions")
def list_transactions(
    _: AnalystUser,
    db: DbSession,
    filters: Annotated[TransactionFilters, Depends()],
    params: Annotated[PageParams, Depends()],
) -> Page[TransactionRead]:
    base = filters.apply(select(Transaction))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(*_ORDER[filters.sort]).offset(params.offset).limit(params.page_size)
    ).all()
    return Page[TransactionRead](
        items=[TransactionRead.model_validate(r) for r in rows],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetail,
    summary="One transaction",
    responses={404: {"model": ErrorResponse}},
)
def get_transaction(transaction_id: int, _: AnalystUser, db: DbSession) -> TransactionDetail:
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise not_found("Transaction", transaction_id)
    return TransactionDetail.model_validate(tx)
