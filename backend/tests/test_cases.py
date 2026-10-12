import pytest
from sqlalchemy import select

from app.models import AuditEvent, Case
from app.models.enums import Role

pytestmark = pytest.mark.usefixtures("scored")


def alert_ids(client, headers, n: int = 2) -> list[int]:
    items = client.get(f"/api/v1/alerts?page_size={n}", headers=headers).json()["items"]
    assert len(items) == n
    return [i["id"] for i in items]


def open_case(client, headers, **body):
    payload = {"title": "Rapid transfer then cash-out", "priority": "high", **body}
    return client.post("/api/v1/cases", json=payload, headers=headers)


def test_create_case_with_alerts_assigns_creator_and_audits(client, people, db):
    analyst, h = people["analyst"]
    ids = alert_ids(client, h)
    resp = open_case(client, h, alert_ids=ids, description="Two linked alerts")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reference"] == f"CASE-{body['id']:06d}"
    assert body["status"] == "open" and body["priority"] == "high"
    assert body["assignee"]["id"] == analyst.id and body["created_by"]["id"] == analyst.id
    assert sorted(a["id"] for a in body["alerts"]) == sorted(ids)
    assert all(a["case_reference"] == body["reference"] for a in body["alerts"])
    assert body["timeline"][0]["action"] == "case.created"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "case.created"))
    assert event.after["alert_ids"] == ids and event.actor_id == analyst.id


def test_alert_queue_and_transaction_show_the_case(client, people):
    _, h = people["analyst"]
    aid = alert_ids(client, h, 1)[0]
    case = open_case(client, h, alert_ids=[aid]).json()
    alert = client.get(f"/api/v1/alerts/{aid}", headers=h).json()
    assert alert["case_id"] == case["id"] and alert["case_reference"] == case["reference"]
    linked = client.get("/api/v1/alerts?in_case=true&page_size=200", headers=h).json()
    assert [a["id"] for a in linked["items"]] == [aid]
    unlinked = client.get("/api/v1/alerts?in_case=false&page_size=200", headers=h).json()
    assert aid not in [a["id"] for a in unlinked["items"]]
    tx = client.get(f"/api/v1/transactions/{alert['transaction']['id']}", headers=h).json()
    assert tx["alerts"][0]["case_reference"] == case["reference"]


def test_an_alert_belongs_to_one_case_only(client, people):
    _, h = people["analyst"]
    aid = alert_ids(client, h, 1)[0]
    first = open_case(client, h, alert_ids=[aid]).json()
    resp = open_case(client, h, alert_ids=[aid])
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALERT_ALREADY_IN_CASE"
    assert resp.json()["error"]["details"] == [aid]
    # The failed create left nothing behind.
    listing = client.get("/api/v1/cases", headers=h).json()
    assert [c["id"] for c in listing["items"]] == [first["id"]]
    # Linking the same alert to its own case again is a no-op.
    again = client.post(f"/api/v1/cases/{first['id']}/alerts", json={"alert_ids": [aid]}, headers=h)
    assert again.status_code == 200 and again.json()["alert_count"] == 1


def test_unknown_alert_is_404(client, people):
    _, h = people["analyst"]
    resp = open_case(client, h, alert_ids=[999999])
    assert resp.status_code == 404
    assert resp.json()["error"]["details"] == [999999]


def test_link_and_unlink_are_audited(client, people, db):
    _, h = people["analyst"]
    a1, a2 = alert_ids(client, h)
    case = open_case(client, h).json()
    url = f"/api/v1/cases/{case['id']}/alerts"
    assert client.post(url, json={"alert_ids": [a1, a2]}, headers=h).json()["alert_count"] == 2
    resp = client.delete(f"{url}/{a1}", headers=h)
    assert resp.status_code == 200 and [a["id"] for a in resp.json()["alerts"]] == [a2]
    assert client.delete(f"{url}/{a1}", headers=h).status_code == 404
    actions = [e["action"] for e in client.get(f"/api/v1/cases/{case['id']}", headers=h).json()[
        "timeline"
    ]]  # fmt: skip
    assert actions == ["case.created", "case.alerts_linked", "case.alert_unlinked"]


def test_analysts_work_their_own_cases(client, people, make_user):
    _, h = people["analyst"]
    other, other_h = people["other"]
    _, senior_h = people["senior"]
    case = open_case(client, h).json()
    url = f"/api/v1/cases/{case['id']}"
    # Someone else's case: no changes, no links, no assigning it to yourself.
    assert client.patch(url, json={"status": "investigating"}, headers=other_h).status_code == 403
    assert client.patch(url, json={"assignee_id": other.id}, headers=other_h).status_code == 403
    aid = alert_ids(client, h, 1)[0]
    resp = client.post(f"{url}/alerts", json={"alert_ids": [aid]}, headers=other_h)
    assert resp.status_code == 403
    # Analysts cannot assign cases to others, even when creating them.
    assert open_case(client, h, assignee_id=other.id).status_code == 403
    # A senior can reassign; then the new assignee can work it.
    assert client.patch(url, json={"assignee_id": other.id}, headers=senior_h).status_code == 200
    assert client.patch(url, json={"status": "investigating"}, headers=other_h).status_code == 200
    inactive = make_user(Role.ANALYST, is_active=False)
    resp = client.patch(url, json={"assignee_id": inactive.id}, headers=senior_h)
    assert resp.status_code == 422


def test_unassigned_case_is_taken_by_whoever_works_it(client, people):
    analyst, h = people["analyst"]
    _, senior_h = people["senior"]
    case = open_case(client, senior_h, assignee_id=None).json()
    assert case["assignee"] is None
    resp = client.patch(f"/api/v1/cases/{case['id']}", json={"priority": "critical"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["assignee"]["id"] == analyst.id
    assert resp.json()["priority"] == "critical"


def test_status_flow_and_closing_needs_a_decision(client, people):
    _, h = people["analyst"]
    case = open_case(client, h).json()
    url = f"/api/v1/cases/{case['id']}"
    for status in ("investigating", "pending_decision", "investigating", "pending_decision"):
        assert client.patch(url, json={"status": status}, headers=h).json()["status"] == status
    resp = client.patch(url, json={"status": "closed"}, headers=h)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DECISION_REQUIRED"


def test_only_seniors_decide_and_a_rationale_is_required(client, people, db):
    _, h = people["analyst"]
    senior, senior_h = people["senior"]
    case = open_case(client, h, alert_ids=alert_ids(client, h, 1)).json()
    url = f"/api/v1/cases/{case['id']}/decision"
    decision = {"decision": "escalate_for_reporting", "rationale": "Funds moved to a mule account."}
    assert client.post(url, json=decision, headers=h).status_code == 403
    short = client.post(url, json={**decision, "rationale": "  bad    "}, headers=senior_h)
    assert short.status_code == 422
    resp = client.post(url, json=decision, headers=senior_h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "closed" and body["decision"] == "escalate_for_reporting"
    assert body["decided_by"]["id"] == senior.id and body["decided_at"] is not None
    assert body["decision_rationale"] == decision["rationale"]
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "case.decided"))
    assert event.before["status"] == "open" and event.after["decision"] == "escalate_for_reporting"
    # Decided once: a second decision is refused.
    assert client.post(url, json=decision, headers=senior_h).status_code == 409


def test_closed_cases_are_final_but_accept_notes(client, people):
    _, h = people["analyst"]
    _, senior_h = people["senior"]
    a1, a2 = alert_ids(client, h)
    case = open_case(client, h, alert_ids=[a1]).json()
    url = f"/api/v1/cases/{case['id']}"
    decision = {"decision": "false_positive", "rationale": "Customer confirmed the payment."}
    client.post(f"{url}/decision", json=decision, headers=senior_h)
    for resp in (
        client.patch(url, json={"priority": "low"}, headers=senior_h),
        client.patch(url, json={"assignee_id": None}, headers=senior_h),
        client.post(f"{url}/alerts", json={"alert_ids": [a2]}, headers=senior_h),
        client.delete(f"{url}/alerts/{a1}", headers=senior_h),
    ):
        assert resp.status_code == 409 and resp.json()["error"]["code"] == "CASE_CLOSED"
    # Sending the unchanged values is a no-op, not an error.
    assert client.patch(url, json={"priority": "high"}, headers=senior_h).status_code == 200
    note = client.post(f"{url}/notes", json={"body": "Addendum after closure."}, headers=h)
    assert note.status_code == 201


def test_notes_are_append_only_and_audited(client, people, db):
    analyst, h = people["analyst"]
    _, other_h = people["other"]
    case = open_case(client, h).json()
    url = f"/api/v1/cases/{case['id']}/notes"
    assert client.post(url, json={"body": "   "}, headers=h).status_code == 422
    first = client.post(url, json={"body": "  Checked KYC file.  "}, headers=h).json()
    assert first["body"] == "Checked KYC file." and first["author"]["id"] == analyst.id
    # Any analyst can add notes, including to cases they are not assigned to.
    assert client.post(url, json={"body": "Second opinion."}, headers=other_h).status_code == 201
    detail = client.get(f"/api/v1/cases/{case['id']}", headers=h).json()
    assert [n["body"] for n in detail["notes"]] == ["Checked KYC file.", "Second opinion."]
    assert detail["note_count"] == 2
    # No edit or delete endpoints exist.
    note_url = f"{url}/{first['id']}"
    assert client.patch(note_url, json={"body": "x"}, headers=h).status_code in (404, 405)
    assert client.delete(note_url, headers=h).status_code in (404, 405)
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "case.note_added"))


def test_updates_are_audited_only_when_something_changes(client, people, db):
    _, h = people["analyst"]
    case = open_case(client, h).json()
    url = f"/api/v1/cases/{case['id']}"
    client.patch(url, json={"priority": "high"}, headers=h)  # unchanged
    client.patch(url, json={"priority": "critical", "title": "Renamed case"}, headers=h)
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "case.updated")).all()
    assert len(events) == 1
    assert events[0].before["priority"] == "high" and events[0].after["priority"] == "critical"
    assert events[0].after["title"] == "Renamed case"


def test_list_filters_search_and_counts(client, people):
    analyst, h = people["analyst"]
    _, senior_h = people["senior"]
    mine = open_case(client, h, title="Mule network A", alert_ids=alert_ids(client, h, 1)).json()
    theirs = open_case(client, senior_h, title="Other work", priority="low").json()

    def ids(query: str) -> list[int]:
        resp = client.get(f"/api/v1/cases{query}", headers=h)
        assert resp.status_code == 200, resp.text
        return [c["id"] for c in resp.json()["items"]]

    assert set(ids("")) == {mine["id"], theirs["id"]}
    assert ids("?assigned_to_me=true") == [mine["id"]]
    assert ids(f"?assignee_id={analyst.id}") == [mine["id"]]
    assert ids("?priority=low") == [theirs["id"]]
    assert ids("?q=mule") == [mine["id"]]
    assert ids(f"?q={theirs['reference']}") == [theirs["id"]]
    assert ids("?q=%25") == []  # LIKE wildcards are escaped
    assert ids("?status=closed") == []
    assert ids("?sort=-priority")[0] == mine["id"]
    row = next(
        c for c in client.get("/api/v1/cases", headers=h).json()["items"] if c["id"] == mine["id"]
    )
    assert row["alert_count"] == 1 and row["note_count"] == 0


def test_case_validation_and_404(client, people):
    _, h = people["analyst"]
    assert open_case(client, h, title="  ").status_code == 422
    assert open_case(client, h, priority="urgent").status_code == 422
    assert client.get("/api/v1/cases/999", headers=h).status_code == 404
    assert client.patch("/api/v1/cases/999", json={}, headers=h).status_code == 404
    resp = client.post("/api/v1/cases/999/notes", json={"body": "x"}, headers=h)
    assert resp.status_code == 404


def test_cases_require_login(client):
    assert client.get("/api/v1/cases").status_code == 401
    assert client.post("/api/v1/cases", json={"title": "abc"}).status_code == 401


def test_assignable_users_lists_active_people(client, people, make_user):
    _, h = people["analyst"]
    inactive = make_user(Role.ANALYST, is_active=False)
    users = client.get("/api/v1/users/assignable", headers=h).json()
    ids = {u["id"] for u in users}
    assert {p[0].id for p in people.values()} <= ids and inactive.id not in ids
    assert set(users[0]) == {"id", "full_name", "role"}  # no emails or other details


def test_reference_matches_id_for_many_cases(client, people, db):
    _, h = people["analyst"]
    for i in range(3):
        open_case(client, h, title=f"Case number {i}")
    for case in db.scalars(select(Case)).all():
        assert case.reference == f"CASE-{case.id:06d}"
