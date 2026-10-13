from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.models import AuditEvent, MonitoringRule
from app.models.enums import Role, TransactionType
from app.services.rules import TxFacts, evaluate_rule, validate_parameters


def facts(**overrides) -> TxFacts:
    base = dict(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000"),
        origin_balance_before=Decimal("500000"),
        dest_account="C9",
        dest_prior_in=0,
        origin_recent_count=0,
    )
    return TxFacts(**(base | overrides))


@pytest.mark.parametrize(
    ("rule_type", "params", "overrides", "fires"),
    [
        ("large_amount", {"min_amount": "100000", "types": ["TRANSFER"]}, {}, True),
        ("large_amount", {"min_amount": "100000", "types": ["CASH_OUT"]}, {}, False),
        ("large_amount", {"min_amount": "900000", "types": ["TRANSFER"]}, {}, False),
        ("balance_drain", {"min_amount": "0", "types": ["TRANSFER"]}, {}, True),
        (
            "balance_drain",
            {"min_amount": "0", "types": ["TRANSFER"]},
            {"origin_balance_before": Decimal("0")},
            False,
        ),
        (
            "balance_drain",
            {"min_amount": "0", "types": ["TRANSFER"]},
            {"origin_balance_before": Decimal("600000")},
            False,
        ),
        ("new_destination", {"min_amount": "1", "types": ["TRANSFER"]}, {}, True),
        (
            "new_destination",
            {"min_amount": "1", "types": ["TRANSFER"]},
            {"dest_prior_in": 2},
            False,
        ),
        (
            "new_destination",
            {"min_amount": "1", "types": ["TRANSFER"]},
            {"dest_account": "M1"},
            False,
        ),
        ("origin_velocity", {"window_hours": 24, "max_count": 3}, {"origin_recent_count": 3}, True),
        (
            "origin_velocity",
            {"window_hours": 24, "max_count": 3},
            {"origin_recent_count": 2},
            False,
        ),
    ],
)
def test_rule_types(rule_type, params, overrides, fires):
    assert (evaluate_rule(rule_type, params, facts(**overrides)) is not None) is fires


@pytest.mark.parametrize(
    ("rule_type", "params"),
    [
        ("large_amount", {"min_amount": "-1", "types": ["TRANSFER"]}),
        ("large_amount", {"min_amount": "10", "types": []}),
        ("large_amount", {"min_amount": "10", "types": ["WIRE"]}),
        ("origin_velocity", {"window_hours": 0, "max_count": 3}),
        ("origin_velocity", {"window_hours": 24, "max_count": 3, "extra": 1}),
        ("made_up_type", {}),
    ],
)
def test_invalid_parameters_are_rejected(rule_type, params):
    with pytest.raises(AppError) as exc:
        validate_parameters(rule_type, params)
    assert exc.value.status_code == 422


def test_default_rules_are_seeded(client, make_user, login):
    rules = client.get("/api/v1/rules", headers=login(make_user(Role.ANALYST))).json()
    assert {r["code"] for r in rules} == {
        "LARGE_TRANSFER",
        "BALANCE_DRAIN",
        "NEW_DESTINATION",
        "ORIGIN_VELOCITY",
    }


def _rule_id(db, code: str) -> int:
    return db.scalar(select(MonitoringRule.id).where(MonitoringRule.code == code))


@pytest.mark.parametrize("role", [Role.ANALYST, Role.SENIOR_ANALYST])
def test_only_admin_can_edit_rules(client, make_user, login, db, role):
    rid = _rule_id(db, "LARGE_TRANSFER")
    resp = client.patch(
        f"/api/v1/rules/{rid}", json={"enabled": False}, headers=login(make_user(role))
    )
    assert resp.status_code == 403


def test_rule_edit_is_validated_and_audited(client, make_user, login, db):
    admin = make_user(Role.ADMIN)
    headers = login(admin)
    rid = _rule_id(db, "LARGE_TRANSFER")
    bad = client.patch(
        f"/api/v1/rules/{rid}", json={"parameters": {"min_amount": "-5"}}, headers=headers
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["details"]

    resp = client.patch(
        f"/api/v1/rules/{rid}",
        json={"parameters": {"min_amount": "5000", "types": ["TRANSFER"]}, "severity": "high"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["parameters"] == {"min_amount": "5000", "types": ["TRANSFER"]}
    assert resp.json()["updated_by_id"] == admin.id
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "rule.updated"))
    assert event.before["parameters"]["min_amount"] == "1000000"
    assert event.after["parameters"]["min_amount"] == "5000"
    assert event.after["severity"] == "high"
    assert client.patch("/api/v1/rules/999", json={}, headers=headers).status_code == 404


@pytest.mark.usefixtures("imported_sample", "active_model")
def test_tuning_a_rule_changes_alert_outcomes(client, make_user, login, db):
    """AT-10: an admin's rule change alters what the next scoring run flags."""
    admin = login(make_user(Role.ADMIN))
    senior = login(make_user(Role.SENIOR_ANALYST))
    for rule in client.get("/api/v1/rules", headers=admin).json():
        client.patch(f"/api/v1/rules/{rule['id']}", json={"enabled": False}, headers=admin)

    # Pick a low-scoring PAYMENT and confirm it raises nothing with all rules off.
    client.post("/api/v1/scoring/run", json={"limit": 5000}, headers=senior)
    calm = client.get(
        "/api/v1/transactions?type=PAYMENT&risk_level=low&has_open_alert=false&page_size=1",
        headers=admin,
    ).json()["items"][0]
    first = client.post(f"/api/v1/scoring/transactions/{calm['id']}", headers=senior).json()
    assert first["alert_id"] is None
    assert not any(c.startswith("RULE_") for c in first["assessment"]["reason_codes"])

    rid = _rule_id(db, "LARGE_TRANSFER")
    client.patch(
        f"/api/v1/rules/{rid}",
        json={
            "enabled": True,
            "severity": "high",
            "parameters": {"min_amount": "0.01", "types": ["PAYMENT"]},
        },
        headers=admin,
    )
    second = client.post(f"/api/v1/scoring/transactions/{calm['id']}", headers=senior).json()
    assert "RULE_LARGE_TRANSFER" in second["assessment"]["reason_codes"]
    assert second["assessment"]["risk_level"] == "high"
    assert second["assessment"]["rule_hits"][0]["code"] == "LARGE_TRANSFER"
    assert second["alert_id"] is not None
