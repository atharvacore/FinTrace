"""Audit trail helper. Call inside the same DB transaction as the change it records."""

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record_audit(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: object,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=before,
        after=after,
        request_id=getattr(request.state, "request_id", None) if request else None,
    )
    db.add(event)
    return event
