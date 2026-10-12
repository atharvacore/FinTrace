import pytest

from app.models.enums import Role


def test_audit_api_is_senior_only_and_filters(client, people, make_user, login):
    _, h = people["analyst"]
    senior, senior_h = people["senior"]
    case = client.post("/api/v1/cases", json={"title": "Audit me"}, headers=h).json()
    client.post(f"/api/v1/cases/{case['id']}/notes", json={"body": "note"}, headers=h)

    assert client.get("/api/v1/audit-events", headers=h).status_code == 403
    assert client.get("/api/v1/audit-events").status_code == 401

    def actions(query: str) -> list[str]:
        resp = client.get(f"/api/v1/audit-events{query}", headers=senior_h)
        assert resp.status_code == 200, resp.text
        return [e["action"] for e in resp.json()["items"]]

    case_filter = f"?entity_type=case&entity_id={case['id']}"
    assert actions(case_filter) == ["case.note_added", "case.created"]  # newest first
    assert actions("?action=case.") == ["case.note_added", "case.created"]
    assert actions("?action=case.created") == ["case.created"]
    assert actions(f"?actor_id={senior.id}") == []
    assert actions("?from=2000-01-01T00:00:00&to=2000-01-02T00:00:00") == []
    event = client.get(f"/api/v1/audit-events{case_filter}", headers=senior_h).json()["items"][-1]
    assert event["actor"]["full_name"] and event["request_id"]
    bad = client.get("/api/v1/audit-events?from=2026-02-01T00:00:00Z&to=2026-01-01T00:00:00Z",
                     headers=senior_h)  # fmt: skip
    assert bad.status_code == 422
    # The audit trail cannot be edited through the API.
    assert client.delete("/api/v1/audit-events", headers=senior_h).status_code == 405


def test_metrics_without_a_model(client, people, imported_sample):
    _, h = people["analyst"]
    body = client.get("/api/v1/metrics/overview", headers=h).json()
    assert body["transactions_total"] == 5000
    assert body["transactions_scored"] == 0 and body["transactions_unscored"] == 5000
    assert body["active_model"] is None and body["alerts_per_1000_scored"] is None
    assert "Synthetic data" in body["notice"]
    for path in ("risk-distribution", "model-evaluation"):
        resp = client.get(f"/api/v1/metrics/{path}", headers=h)
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "MODEL_NOT_AVAILABLE"


@pytest.mark.usefixtures("scored")
def test_overview_counts_match_the_database(client, people, scored):
    analyst, h = people["analyst"]
    _, senior_h = people["senior"]
    alerts = client.get("/api/v1/alerts?page_size=200", headers=h).json()
    first = alerts["items"][0]["id"]
    client.patch(f"/api/v1/alerts/{first}", json={"status": "in_review"}, headers=h)
    case = client.post("/api/v1/cases", json={"title": "Metrics case"}, headers=h).json()
    client.post(
        f"/api/v1/cases/{case['id']}/decision",
        json={"decision": "no_further_action", "rationale": "Explained by payroll."},
        headers=senior_h,
    )

    body = client.get("/api/v1/metrics/overview", headers=h).json()
    assert body["transactions_scored"] == 5000 and body["transactions_unscored"] == 0
    assert body["alerts_total"] == alerts["total"] == scored["alerts_created"]
    assert body["alerts_by_status"]["in_review"] == 1
    assert sum(body["alerts_by_status"].values()) == body["alerts_total"]
    assert sum(body["open_alerts_by_priority"].values()) == body["alerts_total"]
    assert body["alerts_per_1000_scored"] == round(1000 * body["alerts_total"] / 5000, 2)
    assert body["cases_by_status"]["closed"] == 1 and body["decisions"] == {"no_further_action": 1}
    assert body["my_open_alerts"] == 1 and body["my_open_cases"] == 0
    assert body["active_model"]["is_synthetic_demo"] is True
    check = body["label_check"]
    assert check["scored_with_label"] == 5000 and check["labelled_fraud_scored"] == 108
    assert check["alerts_with_label"] == body["alerts_total"]
    assert 0 <= check["labelled_fraud_alerted"] <= 108


@pytest.mark.usefixtures("scored")
def test_risk_distribution_bins_add_up(client, people, db):
    from sqlalchemy import func, select

    from app.models import RiskAssessment

    _, h = people["analyst"]
    body = client.get("/api/v1/metrics/risk-distribution?bins=10", headers=h).json()
    assert (
        len(body["bins"]) == 10 and body["bins"][0]["lower"] == 0 and body["bins"][-1]["upper"] == 1
    )
    assert sum(b["count"] for b in body["bins"]) == body["transactions"] == 5000
    assert sum(b["labelled_fraud"] for b in body["bins"]) == 108
    assert sum(body["by_level"].values()) == 5000
    threshold = float(body["threshold"])
    expected = db.scalar(select(func.count()).where(RiskAssessment.risk_score >= threshold))
    assert body["above_threshold"] == expected
    assert client.get("/api/v1/metrics/risk-distribution?bins=2", headers=h).status_code == 422


@pytest.mark.usefixtures("scored")
def test_rescoring_does_not_double_count_the_distribution(client, people):
    _, h = people["analyst"]
    _, senior_h = people["senior"]
    tx_id = client.get("/api/v1/transactions?page_size=1", headers=h).json()["items"][0]["id"]
    client.post(f"/api/v1/scoring/transactions/{tx_id}", headers=senior_h)
    body = client.get("/api/v1/metrics/risk-distribution", headers=h).json()
    assert body["transactions"] == 5000


@pytest.mark.usefixtures("active_model")
def test_model_evaluation_returns_stored_metrics_and_caveats(client, make_user, login):
    h = login(make_user(Role.ANALYST))
    body = client.get("/api/v1/metrics/model-evaluation", headers=h).json()
    assert body["is_synthetic_demo"] is True
    assert any("NOT results" in c for c in body["caveats"])
    assert any("not confirmed money laundering" in c for c in body["caveats"])
    chosen = body["selection"]["chosen"]
    assert {"validation", "test"} <= set(body["models"][chosen])
    assert "average_precision" in body["models"][chosen]["test"]
    assert body["split"]["method"].startswith("chronological")
