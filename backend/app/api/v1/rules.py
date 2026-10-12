from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import AdminUser, AnalystUser, DbSession
from app.core.errors import not_found
from app.models import MonitoringRule
from app.schemas.common import ErrorResponse
from app.schemas.scoring import RuleRead, RuleUpdate
from app.services.audit import record_audit
from app.services.rules import validate_parameters

router = APIRouter(
    prefix="/rules",
    tags=["rules"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


def _snapshot(rule: MonitoringRule) -> dict:
    return {
        "name": rule.name,
        "parameters": rule.parameters,
        "severity": rule.severity.value,
        "enabled": rule.enabled,
    }


@router.get("", response_model=list[RuleRead], summary="Monitoring rules")
def list_rules(_: AnalystUser, db: DbSession) -> list[MonitoringRule]:
    return list(db.scalars(select(MonitoringRule).order_by(MonitoringRule.id)))


@router.patch(
    "/{rule_id}",
    response_model=RuleRead,
    summary="Tune a rule (parameters are validated against the rule type)",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_rule(
    rule_id: int, body: RuleUpdate, admin: AdminUser, db: DbSession, request: Request
) -> MonitoringRule:
    rule = db.get(MonitoringRule, rule_id)
    if rule is None:
        raise not_found("Rule", rule_id)
    before = _snapshot(rule)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "parameters" in changes:
        changes["parameters"] = validate_parameters(rule.rule_type, changes["parameters"])
    for field, value in changes.items():
        setattr(rule, field, value)
    rule.updated_by_id = admin.id
    record_audit(
        db,
        actor=admin,
        action="rule.updated",
        entity_type="monitoring_rule",
        entity_id=rule.id,
        before=before,
        after=_snapshot(rule),
        request=request,
    )
    db.commit()
    db.refresh(rule)
    return rule
