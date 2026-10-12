from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, select

from app.api.deps import DbSession, SeniorUser
from app.core.errors import AppError
from app.models import AuditEvent
from app.schemas.case import AuditEventRead
from app.schemas.common import ErrorResponse, Page, PageParams

router = APIRouter(
    prefix="/audit-events",
    tags=["audit"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class AuditFilters:
    def __init__(
        self,
        entity_type: Annotated[str | None, Query(max_length=64)] = None,
        entity_id: Annotated[str | None, Query(max_length=64)] = None,
        actor_id: int | None = None,
        action: Annotated[
            str | None, Query(max_length=64, description="Exact action, or a prefix like 'case.'")
        ] = None,
        occurred_from: Annotated[datetime | None, Query(alias="from")] = None,
        occurred_to: Annotated[datetime | None, Query(alias="to")] = None,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.actor_id = actor_id
        self.action = action
        self.occurred_from = _utc(occurred_from)
        self.occurred_to = _utc(occurred_to)
        if self.occurred_from and self.occurred_to and self.occurred_from > self.occurred_to:
            raise AppError(422, "VALIDATION_ERROR", "'from' must not be after 'to'")

    def apply(self, stmt: Select) -> Select:
        if self.entity_type:
            stmt = stmt.where(AuditEvent.entity_type == self.entity_type)
        if self.entity_id:
            stmt = stmt.where(AuditEvent.entity_id == self.entity_id)
        if self.actor_id is not None:
            stmt = stmt.where(AuditEvent.actor_id == self.actor_id)
        if self.action:
            if self.action.endswith("."):
                stmt = stmt.where(AuditEvent.action.startswith(self.action, autoescape=True))
            else:
                stmt = stmt.where(AuditEvent.action == self.action)
        if self.occurred_from:
            stmt = stmt.where(AuditEvent.created_at >= self.occurred_from)
        if self.occurred_to:
            stmt = stmt.where(AuditEvent.created_at <= self.occurred_to)
        return stmt


@router.get(
    "",
    response_model=Page[AuditEventRead],
    summary="Audit trail (senior analyst), newest first",
    description="Append-only record of sensitive changes. There is no endpoint to edit or delete.",
)
def list_audit_events(
    _: SeniorUser,
    db: DbSession,
    filters: Annotated[AuditFilters, Depends()],
    params: Annotated[PageParams, Depends()],
) -> Page[AuditEventRead]:
    base = filters.apply(select(AuditEvent))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    events = db.scalars(
        base.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).unique()
    return Page[AuditEventRead](
        items=[AuditEventRead.model_validate(e) for e in events],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )
