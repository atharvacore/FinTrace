from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import Select, case, func, or_, select

from app.api.deps import AnalystUser, DbSession
from app.api.v1.alerts import to_alert_read
from app.core.errors import AppError, not_found
from app.models import Alert, AuditEvent, Case, CaseAlert, CaseNote
from app.models.enums import CaseStatus, RiskLevel
from app.schemas.case import (
    AuditEventRead,
    CaseCreate,
    CaseDetail,
    CaseLinkAlerts,
    CaseRead,
    CaseUpdate,
    DecisionCreate,
    NoteCreate,
    NoteRead,
)
from app.schemas.common import ErrorResponse, Page, PageParams
from app.services import cases as svc
from app.services.audit import record_audit

router = APIRouter(
    prefix="/cases",
    tags=["cases"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)

ALERT_COUNT = (
    select(func.count()).where(CaseAlert.case_id == Case.id).correlate(Case).scalar_subquery()
)
NOTE_COUNT = (
    select(func.count()).where(CaseNote.case_id == Case.id).correlate(Case).scalar_subquery()
)
PRIORITY_RANK = case(
    {RiskLevel.CRITICAL: 4, RiskLevel.HIGH: 3, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 1},
    value=Case.priority,
)


class CaseSort(StrEnum):
    UPDATED = "-updated_at"
    NEWEST = "-created_at"
    OLDEST = "created_at"
    PRIORITY = "-priority"


_ORDER = {
    CaseSort.UPDATED: (Case.updated_at.desc(), Case.id.desc()),
    CaseSort.NEWEST: (Case.created_at.desc(), Case.id.desc()),
    CaseSort.OLDEST: (Case.created_at.asc(), Case.id.asc()),
    CaseSort.PRIORITY: (PRIORITY_RANK.desc(), Case.updated_at.desc(), Case.id.desc()),
}


class CaseFilters:
    def __init__(
        self,
        status: Annotated[list[CaseStatus] | None, Query()] = None,
        priority: Annotated[list[RiskLevel] | None, Query()] = None,
        assignee_id: int | None = None,
        assigned_to_me: bool = False,
        unassigned: bool = False,
        q: Annotated[str | None, Query(max_length=100, description="Reference or title")] = None,
        sort: CaseSort = CaseSort.UPDATED,
    ) -> None:
        self.status = status
        self.priority = priority
        self.assignee_id = assignee_id
        self.assigned_to_me = assigned_to_me
        self.unassigned = unassigned
        self.q = q.strip() if q else None
        self.sort = sort

    def apply(self, stmt: Select, user_id: int) -> Select:
        if self.status:
            stmt = stmt.where(Case.status.in_(self.status))
        if self.priority:
            stmt = stmt.where(Case.priority.in_(self.priority))
        if self.assignee_id is not None:
            stmt = stmt.where(Case.assignee_id == self.assignee_id)
        if self.assigned_to_me:
            stmt = stmt.where(Case.assignee_id == user_id)
        if self.unassigned:
            stmt = stmt.where(Case.assignee_id.is_(None))
        if self.q:
            pattern = "%" + self.q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            pattern += "%"
            stmt = stmt.where(or_(Case.reference.ilike(pattern), Case.title.ilike(pattern)))
        return stmt


def _fields(case_: Case, model: type[CaseRead]) -> dict:
    """Case attributes for a response model (counts and lists are added by the caller)."""
    computed = {"alert_count", "note_count", "alerts", "notes", "timeline"}
    return {f: getattr(case_, f) for f in model.model_fields if f not in computed}


def _to_read(case_: Case, alert_count: int, note_count: int) -> CaseRead:
    return CaseRead.model_validate(
        {**_fields(case_, CaseRead), "alert_count": alert_count, "note_count": note_count}
    )


def _detail(db: DbSession, case_: Case) -> CaseDetail:
    alerts = db.scalars(
        select(Alert)
        .join(CaseAlert, CaseAlert.alert_id == Alert.id)
        .where(CaseAlert.case_id == case_.id)
        .order_by(CaseAlert.linked_at, Alert.id)
    ).unique()
    notes = db.scalars(
        select(CaseNote).where(CaseNote.case_id == case_.id).order_by(CaseNote.created_at)
    ).all()
    timeline = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "case", AuditEvent.entity_id == str(case_.id))
        .order_by(AuditEvent.created_at, AuditEvent.id)
    ).all()
    alert_reads = [to_alert_read(a, case_.id, case_.reference) for a in alerts]
    return CaseDetail.model_validate(
        {
            **_fields(case_, CaseDetail),
            "alert_count": len(alert_reads),
            "note_count": len(notes),
            "alerts": alert_reads,
            "notes": [NoteRead.model_validate(n) for n in notes],
            "timeline": [AuditEventRead.model_validate(e) for e in timeline],
        }
    )


def _locked_case(db: DbSession, case_id: int) -> Case:
    case_ = db.scalar(select(Case).where(Case.id == case_id).with_for_update(of=Case))
    if case_ is None:
        raise not_found("Case", case_id)
    return case_


@router.get("", response_model=Page[CaseRead], summary="List cases")
def list_cases(
    user: AnalystUser,
    db: DbSession,
    filters: Annotated[CaseFilters, Depends()],
    params: Annotated[PageParams, Depends()],
) -> Page[CaseRead]:
    base = filters.apply(select(Case), user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.add_columns(ALERT_COUNT, NOTE_COUNT)
        .order_by(*_ORDER[filters.sort])
        .offset(params.offset)
        .limit(params.page_size)
    ).unique()
    return Page[CaseRead](
        items=[_to_read(c, ac, nc) for c, ac, nc in rows],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.post(
    "",
    response_model=CaseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Open a case, optionally linking alerts",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_case(body: CaseCreate, user: AnalystUser, db: DbSession, request: Request) -> CaseDetail:
    assignee_id = user.id if "assignee_id" not in body.model_fields_set else body.assignee_id
    svc.check_assignee(db, user, assignee_id, current=None)
    case_id, reference = svc.next_reference(db)
    case_ = Case(
        id=case_id,
        reference=reference,
        title=body.title,
        description=body.description,
        priority=body.priority,
        assignee_id=assignee_id,
        created_by_id=user.id,
        status=CaseStatus.OPEN,
    )
    db.add(case_)
    db.flush()
    linked = svc.link_alerts(db, case_, body.alert_ids, user) if body.alert_ids else []
    record_audit(
        db,
        actor=user,
        action="case.created",
        entity_type="case",
        entity_id=case_.id,
        after={**svc.snapshot(case_), "reference": reference, "alert_ids": linked},
        request=request,
    )
    db.commit()
    db.refresh(case_)
    return _detail(db, case_)


@router.get(
    "/{case_id}",
    response_model=CaseDetail,
    summary="Case with alerts, notes and audit timeline",
    responses={404: {"model": ErrorResponse}},
)
def get_case(case_id: int, _: AnalystUser, db: DbSession) -> CaseDetail:
    case_ = db.get(Case, case_id)
    if case_ is None:
        raise not_found("Case", case_id)
    return _detail(db, case_)


@router.patch(
    "/{case_id}",
    response_model=CaseDetail,
    summary="Change title, description, status, priority or assignee",
    description=(
        "Analysts may change cases assigned to them (changing an unassigned case assigns it to "
        "you) and may only assign cases to themselves. Senior analysts may change and assign any "
        "case. Closing requires a decision. Closed cases cannot change (409)."
    ),
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_case(
    case_id: int, body: CaseUpdate, user: AnalystUser, db: DbSession, request: Request
) -> CaseDetail:
    case_ = _locked_case(db, case_id)
    before = svc.snapshot(case_)
    # null means "unassign" for assignee_id and "no change" for every other field.
    requested = {
        f: getattr(body, f)
        for f in body.model_fields_set
        if f == "assignee_id" or getattr(body, f) is not None
    }
    changes = {f: v for f, v in requested.items() if getattr(case_, f) != v}
    if changes and case_.status == CaseStatus.CLOSED:
        raise svc.closed_error(case_)

    if "assignee_id" in changes:
        svc.check_assignee(db, user, changes.pop("assignee_id"), current=case_.assignee_id)
        case_.assignee_id = body.assignee_id
    if changes:
        svc.ensure_can_work(case_, user)
        if "status" in changes:
            svc.set_status(case_, changes.pop("status"))
        for field, value in changes.items():
            setattr(case_, field, value)

    after = svc.snapshot(case_)
    if after != before or "description" in changes:
        record_audit(
            db,
            actor=user,
            action="case.updated",
            entity_type="case",
            entity_id=case_.id,
            before=before,
            after={**after, "description_changed": "description" in changes},
            request=request,
        )
    db.commit()
    db.refresh(case_)
    return _detail(db, case_)


@router.post(
    "/{case_id}/alerts",
    response_model=CaseDetail,
    summary="Link alerts to the case",
    description="An alert can belong to only one case (409 ALERT_ALREADY_IN_CASE).",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def link_alerts(
    case_id: int, body: CaseLinkAlerts, user: AnalystUser, db: DbSession, request: Request
) -> CaseDetail:
    case_ = _locked_case(db, case_id)
    svc.ensure_can_work(case_, user)
    linked = svc.link_alerts(db, case_, body.alert_ids, user)
    if linked:
        record_audit(
            db,
            actor=user,
            action="case.alerts_linked",
            entity_type="case",
            entity_id=case_.id,
            after={"alert_ids": linked},
            request=request,
        )
    db.commit()
    db.refresh(case_)
    return _detail(db, case_)


@router.delete(
    "/{case_id}/alerts/{alert_id}",
    response_model=CaseDetail,
    summary="Unlink an alert from the case",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def unlink_alert(
    case_id: int, alert_id: int, user: AnalystUser, db: DbSession, request: Request
) -> CaseDetail:
    case_ = _locked_case(db, case_id)
    link = db.get(CaseAlert, (case_id, alert_id))
    if link is None:
        raise AppError(404, "NOT_FOUND", f"Alert {alert_id} is not linked to {case_.reference}")
    svc.ensure_can_work(case_, user)
    db.delete(link)
    record_audit(
        db,
        actor=user,
        action="case.alert_unlinked",
        entity_type="case",
        entity_id=case_.id,
        before={"alert_id": alert_id},
        request=request,
    )
    db.commit()
    db.refresh(case_)
    return _detail(db, case_)


@router.post(
    "/{case_id}/notes",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a note (append-only)",
    description="Any analyst can add notes, also to closed cases. Notes cannot be edited.",
    responses={404: {"model": ErrorResponse}},
)
def add_note(
    case_id: int, body: NoteCreate, user: AnalystUser, db: DbSession, request: Request
) -> CaseNote:
    case_ = db.get(Case, case_id)
    if case_ is None:
        raise not_found("Case", case_id)
    note = CaseNote(case_id=case_.id, author_id=user.id, body=body.body)
    db.add(note)
    db.flush()
    # Touch the case so "recently updated" sorting reflects investigation activity.
    case_.updated_at = func.now()
    record_audit(
        db,
        actor=user,
        action="case.note_added",
        entity_type="case",
        entity_id=case_.id,
        after={"note_id": note.id, "length": len(body.body)},
        request=request,
    )
    db.commit()
    db.refresh(note)
    return note


@router.post(
    "/{case_id}/decision",
    response_model=CaseDetail,
    summary="Record the decision and close the case (senior analyst)",
    description=(
        "The decision is a human judgement recorded with its rationale. FinTrace's scores are "
        "triage signals; they are not evidence that a crime occurred."
    ),
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def decide_case(
    case_id: int, body: DecisionCreate, user: AnalystUser, db: DbSession, request: Request
) -> CaseDetail:
    case_ = _locked_case(db, case_id)
    before = svc.snapshot(case_)
    svc.record_decision(case_, user, body.decision, body.rationale)
    record_audit(
        db,
        actor=user,
        action="case.decided",
        entity_type="case",
        entity_id=case_.id,
        before=before,
        after={**svc.snapshot(case_), "rationale": body.rationale},
        request=request,
    )
    db.commit()
    db.refresh(case_)
    return _detail(db, case_)
