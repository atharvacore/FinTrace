"""Investigation cases: who may change what, alert linking and decisions.

Rules (enforced here, on the server):
- Any analyst can open a case and add notes to any case (notes are append-only).
- Analysts work cases assigned to them; changing an unassigned case assigns it to you.
  Senior analysts and admins can work and assign any case.
- Status moves between open, investigating and pending_decision. A case is closed only by a
  decision from a senior analyst, with a written rationale. A closed case is final: it can still
  receive notes, but its fields and linked alerts no longer change.
- An alert can be linked to at most one case (also enforced by a unique constraint).
"""

from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Alert, Case, CaseAlert, User
from app.models.enums import ROLE_RANK, CaseDecision, CaseStatus, Role

WORKING_STATUSES = {CaseStatus.OPEN, CaseStatus.INVESTIGATING, CaseStatus.PENDING_DECISION}


def is_senior(user: User) -> bool:
    return ROLE_RANK[user.role] >= ROLE_RANK[Role.SENIOR_ANALYST]


def _forbidden(message: str) -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)


def closed_error(case: Case) -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT, "CASE_CLOSED", f"{case.reference} is closed and cannot change"
    )


def snapshot(case: Case) -> dict:
    return {
        "title": case.title,
        "status": case.status.value,
        "priority": case.priority.value,
        "assignee_id": case.assignee_id,
        "decision": case.decision.value if case.decision else None,
    }


def next_reference(db: Session) -> tuple[int, str]:
    """Reserve the next case id so the reference (CASE-000123) can be set on insert."""
    case_id = db.scalar(text("SELECT nextval(pg_get_serial_sequence('cases', 'id'))"))
    return case_id, f"CASE-{case_id:06d}"


def check_assignee(db: Session, actor: User, assignee_id: int | None, current: int | None) -> None:
    """Validate an assignment change. Analysts may only take or release a case themselves."""
    if not is_senior(actor):
        if assignee_id not in (actor.id, None):
            raise _forbidden("Analysts can only assign cases to themselves")
        if current not in (None, actor.id):
            raise _forbidden("This case is assigned to someone else")
    if assignee_id is not None:
        assignee = db.get(User, assignee_id)
        if assignee is None or not assignee.is_active:
            raise AppError(422, "VALIDATION_ERROR", "Assignee must be an active user")


def ensure_can_work(case: Case, actor: User) -> None:
    """Raise unless `actor` may change this case. Taking an unassigned case assigns it."""
    if case.status == CaseStatus.CLOSED:
        raise closed_error(case)
    if is_senior(actor):
        return
    if case.assignee_id is None:
        case.assignee_id = actor.id
    elif case.assignee_id != actor.id:
        raise _forbidden("This case is assigned to someone else")


def set_status(case: Case, new_status: CaseStatus) -> None:
    if new_status == CaseStatus.CLOSED:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "DECISION_REQUIRED",
            "A case is closed by recording a decision: POST /api/v1/cases/{id}/decision",
        )
    case.status = new_status


def link_alerts(db: Session, case: Case, alert_ids: list[int], actor: User) -> list[int]:
    """Link alerts to a case. Returns the ids newly linked (already-linked ones are skipped)."""
    ids = list(dict.fromkeys(alert_ids))
    found = {a.id for a in db.scalars(select(Alert).where(Alert.id.in_(ids))).unique()}
    missing = [i for i in ids if i not in found]
    if missing:
        raise AppError(
            404, "NOT_FOUND", f"Alert(s) not found: {', '.join(map(str, missing))}", missing
        )
    existing = {
        link.alert_id: link.case_id
        for link in db.scalars(
            select(CaseAlert).where(CaseAlert.alert_id.in_(ids)).with_for_update()
        )
    }
    elsewhere = sorted(i for i, cid in existing.items() if cid != case.id)
    if elsewhere:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "ALERT_ALREADY_IN_CASE",
            "An alert can belong to only one case; already linked elsewhere: "
            + ", ".join(map(str, elsewhere)),
            elsewhere,
        )
    new = [i for i in ids if i not in existing]
    for alert_id in new:
        db.add(CaseAlert(case_id=case.id, alert_id=alert_id, linked_by_id=actor.id))
    return new


def record_decision(case: Case, actor: User, decision: CaseDecision, rationale: str) -> None:
    if not is_senior(actor):
        raise _forbidden("Only a senior analyst can record a case decision")
    if case.status == CaseStatus.CLOSED:
        raise closed_error(case)
    case.decision = decision
    case.decision_rationale = rationale
    case.decided_by_id = actor.id
    case.decided_at = datetime.now(UTC)
    case.status = CaseStatus.CLOSED


def case_links(db: Session, alert_ids: list[int]) -> dict[int, tuple[int, str]]:
    """alert id -> (case id, case reference) for the alerts that are linked to a case."""
    if not alert_ids:
        return {}
    rows = db.execute(
        select(CaseAlert.alert_id, Case.id, Case.reference)
        .join(Case, Case.id == CaseAlert.case_id)
        .where(CaseAlert.alert_id.in_(alert_ids))
    ).all()
    return {alert_id: (case_id, ref) for alert_id, case_id, ref in rows}
