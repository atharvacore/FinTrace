from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, case, func, select

from app.api.deps import AnalystUser, CurrentUser, DbSession
from app.core.errors import not_found
from app.models import Alert, CaseAlert, RiskAssessment
from app.models.enums import AlertStatus, RiskLevel
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.scoring import AlertDetail, AlertRead, AlertUpdate, RiskAssessmentRead
from app.schemas.transaction import TransactionRead
from app.services.alerts import apply_update, snapshot
from app.services.audit import record_audit
from app.services.cases import case_links

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)

PRIORITY_RANK = case(
    {RiskLevel.CRITICAL: 4, RiskLevel.HIGH: 3, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 1},
    value=Alert.priority,
)


class AlertSort(StrEnum):
    NEWEST = "-created_at"
    OLDEST = "created_at"
    PRIORITY = "-priority"
    SCORE = "-risk_score"


_ORDER = {
    AlertSort.NEWEST: (Alert.created_at.desc(), Alert.id.desc()),
    AlertSort.OLDEST: (Alert.created_at.asc(), Alert.id.asc()),
    AlertSort.PRIORITY: (PRIORITY_RANK.desc(), RiskAssessment.risk_score.desc(), Alert.id.desc()),
    AlertSort.SCORE: (RiskAssessment.risk_score.desc(), Alert.id.desc()),
}


class AlertFilters:
    def __init__(
        self,
        status: Annotated[list[AlertStatus] | None, Query()] = None,
        priority: Annotated[list[RiskLevel] | None, Query()] = None,
        assignee_id: int | None = None,
        unassigned: bool = False,
        assigned_to_me: bool = False,
        min_score: Annotated[Decimal | None, Query(ge=0, le=1)] = None,
        reason_code: Annotated[str | None, Query(max_length=64)] = None,
        transaction_id: int | None = None,
        in_case: Annotated[
            bool | None, Query(description="true: linked to a case, false: not linked")
        ] = None,
        sort: AlertSort = AlertSort.PRIORITY,
    ) -> None:
        self.status = status
        self.priority = priority
        self.assignee_id = assignee_id
        self.unassigned = unassigned
        self.assigned_to_me = assigned_to_me
        self.min_score = min_score
        self.reason_code = reason_code
        self.transaction_id = transaction_id
        self.in_case = in_case
        self.sort = sort

    def apply(self, stmt: Select, user_id: int) -> Select:
        if self.status:
            stmt = stmt.where(Alert.status.in_(self.status))
        if self.priority:
            stmt = stmt.where(Alert.priority.in_(self.priority))
        if self.assignee_id is not None:
            stmt = stmt.where(Alert.assignee_id == self.assignee_id)
        if self.unassigned:
            stmt = stmt.where(Alert.assignee_id.is_(None))
        if self.assigned_to_me:
            stmt = stmt.where(Alert.assignee_id == user_id)
        if self.min_score is not None:
            stmt = stmt.where(RiskAssessment.risk_score >= self.min_score)
        if self.reason_code:
            stmt = stmt.where(RiskAssessment.reason_codes.contains([self.reason_code]))
        if self.transaction_id is not None:
            stmt = stmt.where(Alert.transaction_id == self.transaction_id)
        if self.in_case is not None:
            linked = select(CaseAlert.alert_id).where(CaseAlert.alert_id == Alert.id).exists()
            stmt = stmt.where(linked if self.in_case else ~linked)
        return stmt


def to_alert_read(
    alert: Alert, case_id: int | None = None, case_reference: str | None = None
) -> AlertRead:
    return AlertRead(
        id=alert.id,
        status=alert.status,
        priority=alert.priority,
        assignee=alert.assignee,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        closed_at=alert.closed_at,
        transaction=TransactionRead.model_validate(alert.transaction),
        risk_score=alert.assessment.risk_score,
        reason_codes=alert.assessment.reason_codes,
        model_version=alert.assessment.model_version,
        case_id=case_id,
        case_reference=case_reference,
    )


def to_alert_detail(db, alert: Alert) -> AlertDetail:
    case_id, ref = case_links(db, [alert.id]).get(alert.id, (None, None))
    return AlertDetail(
        **to_alert_read(alert, case_id, ref).model_dump(),
        assessment=RiskAssessmentRead.model_validate(alert.assessment),
    )


@router.get("", response_model=Page[AlertRead], summary="Alert queue")
def list_alerts(
    user: AnalystUser,
    db: DbSession,
    filters: Annotated[AlertFilters, Depends()],
    params: Annotated[PageParams, Depends()],
) -> Page[AlertRead]:
    base = filters.apply(
        select(Alert).join(RiskAssessment, Alert.risk_assessment_id == RiskAssessment.id), user.id
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    alerts = list(
        db.scalars(
            base.order_by(*_ORDER[filters.sort]).offset(params.offset).limit(params.page_size)
        ).unique()
    )
    links = case_links(db, [a.id for a in alerts])
    return Page[AlertRead](
        items=[to_alert_read(a, *links.get(a.id, (None, None))) for a in alerts],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertDetail,
    summary="One alert with its transaction and assessment",
    responses={404: {"model": ErrorResponse}},
)
def get_alert(alert_id: int, _: AnalystUser, db: DbSession) -> AlertDetail:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise not_found("Alert", alert_id)
    return to_alert_detail(db, alert)


@router.patch(
    "/{alert_id}",
    response_model=AlertDetail,
    summary="Change status and/or assignee",
    description=(
        "Analysts may assign alerts to themselves and work alerts assigned to them (changing "
        "the status of an unassigned alert assigns it to you). Senior analysts may assign "
        "anyone, close escalated alerts and reopen closed ones. Invalid transitions return 409."
    ),
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_alert(
    alert_id: int, body: AlertUpdate, user: CurrentUser, db: DbSession, request: Request
) -> AlertDetail:
    # Lock the row so two analysts cannot make conflicting changes at the same moment.
    alert = db.scalar(select(Alert).where(Alert.id == alert_id).with_for_update(of=Alert))
    if alert is None:
        raise not_found("Alert", alert_id)
    before = snapshot(alert)
    apply_update(
        db,
        alert,
        user,
        new_status=body.status,
        assignee_set="assignee_id" in body.model_fields_set,
        assignee_id=body.assignee_id,
    )
    after = snapshot(alert)
    if after != before:
        record_audit(
            db,
            actor=user,
            action="alert.updated",
            entity_type="alert",
            entity_id=alert.id,
            before=before,
            after=after,
            request=request,
        )
    db.commit()
    db.refresh(alert)
    return to_alert_detail(db, alert)
