import pytest
from sqlalchemy import func, select

from app.models import Alert, AuditEvent
from app.models.enums import Role


@pytest.fixture
def scored(client, make_user, login, imported_sample, active_model):
    senior = login(make_user(Role.SENIOR_ANALYST))
    resp = client.post("/api/v1/scoring/run", json={"limit": 5000}, headers=senior).json()
    assert resp["alerts_created"] >= 3
    return resp


@pytest.fixture
def people(make_user, login):
    analyst = make_user(Role.ANALYST)
    other = make_user(Role.ANALYST)
    senior = make_user(Role.SENIOR_ANALYST)
    return {
        "analyst": (analyst, login(analyst)),
        "other": (other, login(other)),
        "senior": (senior, login(senior)),
    }


def first_alert_id(client, headers, **query) -> int:
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    return client.get(f"/api/v1/alerts?{qs}", headers=headers).json()["items"][0]["id"]


def patch(client, headers, alert_id, **body):
    return client.patch(f"/api/v1/alerts/{alert_id}", json=body, headers=headers)


@pytest.mark.usefixtures("scored")
def test_alert_queue_lists_priority_score_and_reasons(client, people):
    _, h = people["analyst"]
    body = client.get("/api/v1/alerts?page_size=200", headers=h).json()
    assert body["total"] > 0
    item = body["items"][0]
    for key in ("priority", "status", "risk_score", "reason_codes", "transaction", "model_version"):
        assert key in item
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    priorities = [ranks[i["priority"]] for i in body["items"]]
    assert priorities == sorted(priorities, reverse=True)  # default sort: priority first


@pytest.mark.usefixtures("scored")
def test_alert_filters(client, people):
    _, h = people["analyst"]
    total = client.get("/api/v1/alerts", headers=h).json()["total"]
    crit = client.get("/api/v1/alerts?priority=critical", headers=h).json()
    assert all(i["priority"] == "critical" for i in crit["items"])
    high_score = client.get("/api/v1/alerts?min_score=0.9&page_size=200", headers=h).json()
    assert all(float(i["risk_score"]) >= 0.9 for i in high_score["items"])
    reason = client.get("/api/v1/alerts?reason_code=HIGH_RISK_TYPE&page_size=200", headers=h).json()
    assert all("HIGH_RISK_TYPE" in i["reason_codes"] for i in reason["items"])
    assert client.get("/api/v1/alerts?unassigned=true", headers=h).json()["total"] == total
    assert client.get("/api/v1/alerts?assigned_to_me=true", headers=h).json()["total"] == 0
    by_score = client.get("/api/v1/alerts?sort=-risk_score&page_size=200", headers=h).json()
    scores = [float(i["risk_score"]) for i in by_score["items"]]
    assert scores == sorted(scores, reverse=True)
    assert client.get("/api/v1/alerts?status=bogus", headers=h).status_code == 422


@pytest.mark.usefixtures("scored")
def test_analyst_assigns_self_but_not_others(client, people):
    analyst, h = people["analyst"]
    other, _ = people["other"]
    aid = first_alert_id(client, h)
    assert patch(client, h, aid, assignee_id=other.id).status_code == 403
    resp = patch(client, h, aid, assignee_id=analyst.id)
    assert resp.status_code == 200
    assert resp.json()["assignee"]["id"] == analyst.id
    mine = client.get("/api/v1/alerts?assigned_to_me=true", headers=h).json()
    assert [i["id"] for i in mine["items"]] == [aid]


@pytest.mark.usefixtures("scored")
def test_working_an_unassigned_alert_assigns_it(client, people):
    analyst, h = people["analyst"]
    aid = first_alert_id(client, h)
    resp = patch(client, h, aid, status="in_review")
    assert resp.json()["status"] == "in_review"
    assert resp.json()["assignee"]["id"] == analyst.id


@pytest.mark.usefixtures("scored")
def test_analyst_cannot_touch_someone_elses_alert(client, people):
    _, h = people["analyst"]
    _, other_h = people["other"]
    aid = first_alert_id(client, h)
    patch(client, other_h, aid, status="in_review")
    assert patch(client, h, aid, status="closed_false_positive").status_code == 403
    assert patch(client, h, aid, assignee_id=None).status_code == 403


@pytest.mark.usefixtures("scored")
def test_status_transitions_and_closed_at(client, people):
    _, h = people["analyst"]
    _, senior_h = people["senior"]
    aid = first_alert_id(client, h)
    closed = patch(client, h, aid, status="closed_false_positive").json()
    assert closed["closed_at"] is not None
    bad = patch(client, senior_h, aid, status="escalated")
    assert bad.status_code == 409
    assert bad.json()["error"]["code"] == "INVALID_TRANSITION"
    assert patch(client, h, aid, status="in_review").status_code == 403  # reopen: senior only
    reopened = patch(client, senior_h, aid, status="in_review").json()
    assert reopened["status"] == "in_review" and reopened["closed_at"] is None


@pytest.mark.usefixtures("scored")
def test_escalated_alerts_need_a_senior_to_close(client, people):
    _, h = people["analyst"]
    _, senior_h = people["senior"]
    aid = first_alert_id(client, h)
    patch(client, h, aid, status="escalated")
    assert patch(client, h, aid, status="closed_actioned").status_code == 403
    assert patch(client, senior_h, aid, status="closed_actioned").status_code == 200


@pytest.mark.usefixtures("scored")
def test_senior_assigns_anyone_but_only_active_users(client, people, make_user):
    analyst, _ = people["analyst"]
    _, senior_h = people["senior"]
    inactive = make_user(Role.ANALYST, is_active=False)
    aid = first_alert_id(client, senior_h)
    assert patch(client, senior_h, aid, assignee_id=analyst.id).status_code == 200
    resp = patch(client, senior_h, aid, assignee_id=inactive.id)
    assert resp.status_code == 422
    assert patch(client, senior_h, aid, assignee_id=None).json()["assignee"] is None


@pytest.mark.usefixtures("scored")
def test_alert_changes_are_audited_and_no_ops_are_not(client, people, db):
    analyst, h = people["analyst"]
    aid = first_alert_id(client, h)
    patch(client, h, aid, status="in_review")
    patch(client, h, aid, status="in_review")  # no change
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "alert.updated")).all()
    assert len(events) == 1
    assert events[0].before == {"status": "open", "assignee_id": None}
    assert events[0].after == {"status": "in_review", "assignee_id": analyst.id}


@pytest.mark.usefixtures("scored")
def test_alert_detail_and_404(client, people, db):
    _, h = people["analyst"]
    aid = first_alert_id(client, h)
    detail = client.get(f"/api/v1/alerts/{aid}", headers=h).json()
    assert detail["assessment"]["model_version"] == detail["model_version"]
    assert detail["transaction"]["id"]
    assert client.get("/api/v1/alerts/999999", headers=h).status_code == 404
    assert patch(client, h, 999999, status="in_review").status_code == 404
    assert db.scalar(select(func.count()).select_from(Alert)) > 0
