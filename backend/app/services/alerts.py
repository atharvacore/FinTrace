"""Alert workflow: allowed status transitions and who may make them."""

from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Alert, User
from app.models.enums import ROLE_RANK, AlertStatus, Role

CLOSED = {AlertStatus.CLOSED_FALSE_POSITIVE, AlertStatus.CLOSED_ACTIONED}
TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.OPEN: {AlertStatus.IN_REVIEW, AlertStatus.ESCALATED, *CLOSED},
    AlertStatus.IN_REVIEW: {AlertStatus.OPEN, AlertStatus.ESCALATED, *CLOSED},
    AlertStatus.ESCALATED: {AlertStatus.IN_REVIEW, *CLOSED},
    AlertStatus.CLOSED_FALSE_POSITIVE: {AlertStatus.IN_REVIEW},
    AlertStatus.CLOSED_ACTIONED: {AlertStatus.IN_REVIEW},
}


def _is_senior(user: User) -> bool:
    return ROLE_RANK[user.role] >= ROLE_RANK[Role.SENIOR_ANALYST]


def _forbidden(message: str) -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)


def _other_open_alert(db: Session, alert: Alert) -> bool:
    return (
        db.scalar(
            select(Alert.id).where(
                Alert.transaction_id == alert.transaction_id,
                Alert.id != alert.id,
                Alert.status.not_in(CLOSED),
            )
        )
        is not None
    )


def snapshot(alert: Alert) -> dict:
    return {"status": alert.status.value, "assignee_id": alert.assignee_id}


def apply_update(
    db: Session,
    alert: Alert,
    actor: User,
    *,
    new_status: AlertStatus | None,
    assignee_set: bool,
    assignee_id: int | None,
) -> None:
    """Validate and apply a status and/or assignment change. Raises 403/409/422."""
    senior = _is_senior(actor)

    if assignee_set and assignee_id != alert.assignee_id:
        if not senior and assignee_id not in (actor.id, None):
            raise _forbidden("Analysts can only assign alerts to themselves")
        if not senior and assignee_id is None and alert.assignee_id != actor.id:
            raise _forbidden("Analysts can only unassign themselves")
        if not senior and alert.assignee_id not in (None, actor.id):
            raise _forbidden("This alert is assigned to someone else")
        if assignee_id is not None:
            assignee = db.get(User, assignee_id)
            if assignee is None or not assignee.is_active:
                raise AppError(422, "VALIDATION_ERROR", "Assignee must be an active user")
        alert.assignee_id = assignee_id

    if new_status is not None and new_status != alert.status:
        if new_status not in TRANSITIONS[alert.status]:
            raise AppError(
                status.HTTP_409_CONFLICT,
                "INVALID_TRANSITION",
                f"Cannot move an alert from {alert.status.value} to {new_status.value}",
            )
        if not senior:
            if alert.assignee_id is None:
                alert.assignee_id = actor.id  # taking an unassigned alert assigns it to you
            elif alert.assignee_id != actor.id:
                raise _forbidden("This alert is assigned to someone else")
            if alert.status in CLOSED:
                raise _forbidden("Only a senior analyst can reopen a closed alert")
            if alert.status == AlertStatus.ESCALATED:
                # Otherwise an analyst could de-escalate to in_review and then close it.
                raise _forbidden("Only a senior analyst can act on an escalated alert")
        if alert.status in CLOSED and new_status not in CLOSED and _other_open_alert(db, alert):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "ALERT_ALREADY_OPEN",
                "This transaction already has another open alert; work that one instead",
            )
        alert.status = new_status
        alert.closed_at = datetime.now(UTC) if new_status in CLOSED else None
