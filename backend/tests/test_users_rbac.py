import pytest
from sqlalchemy import select

from app.models import AuditEvent
from app.models.enums import Role

NEW_USER = {
    "email": "New.Analyst@example.com",
    "full_name": "New Analyst",
    "role": "analyst",
    "password": "a-long-enough-password",
}


@pytest.mark.parametrize("role", [Role.ANALYST, Role.SENIOR_ANALYST])
def test_non_admins_cannot_manage_users(client, make_user, login, role):
    headers = login(make_user(role))
    assert client.get("/api/v1/users", headers=headers).status_code == 403
    resp = client.post("/api/v1/users", json=NEW_USER, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_unauthenticated_user_management_is_401(client):
    assert client.get("/api/v1/users").status_code == 401


def test_admin_creates_user_and_action_is_audited(client, make_user, login, db):
    admin = make_user(Role.ADMIN)
    resp = client.post(
        "/api/v1/users", json=NEW_USER, headers=login(admin) | {"X-Request-ID": "req-create-1"}
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["email"] == "new.analyst@example.com"
    assert "password" not in created and "password_hash" not in created

    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.created"))
    assert event.actor_id == admin.id
    assert event.entity_id == str(created["id"])
    assert event.request_id == "req-create-1"
    assert "password_hash" not in event.after


def test_duplicate_email_is_rejected_case_insensitively(client, make_user, login):
    headers = login(make_user(Role.ADMIN))
    assert client.post("/api/v1/users", json=NEW_USER, headers=headers).status_code == 201
    dup = NEW_USER | {"email": "NEW.ANALYST@EXAMPLE.COM"}
    resp = client.post("/api/v1/users", json=dup, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


def test_validation_errors_list_fields(client, make_user, login):
    headers = login(make_user(Role.ADMIN))
    bad = NEW_USER | {"password": "short", "role": "superuser", "email": "not-an-email"}
    resp = client.post("/api/v1/users", json=bad, headers=headers)
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    fields = {d["field"] for d in error["details"]}
    assert {"body.password", "body.role", "body.email"} <= fields


def test_role_change_is_audited_with_before_and_after(client, make_user, login, db):
    admin = make_user(Role.ADMIN)
    analyst = make_user(Role.ANALYST)
    resp = client.patch(
        f"/api/v1/users/{analyst.id}", json={"role": "senior_analyst"}, headers=login(admin)
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "senior_analyst"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.updated"))
    assert event.before["role"] == "analyst"
    assert event.after["role"] == "senior_analyst"


def test_password_reset_is_audited_without_secret(client, make_user, login, db):
    admin = make_user(Role.ADMIN)
    analyst = make_user(Role.ANALYST)
    resp = client.patch(
        f"/api/v1/users/{analyst.id}",
        json={"password": "a-brand-new-password"},
        headers=login(admin),
    )
    assert resp.status_code == 200
    login(analyst, password="a-brand-new-password")
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "user.updated"))
    assert event.after["password_changed"] is True
    assert "a-brand-new-password" not in str(event.after)


def test_admin_cannot_demote_or_deactivate_self(client, make_user, login):
    admin = make_user(Role.ADMIN)
    headers = login(admin)
    for change in ({"role": "analyst"}, {"is_active": False}):
        resp = client.patch(f"/api/v1/users/{admin.id}", json=change, headers=headers)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "SELF_LOCKOUT"


def test_update_missing_user_is_404(client, make_user, login):
    resp = client.patch(
        "/api/v1/users/9999", json={"full_name": "X"}, headers=login(make_user(Role.ADMIN))
    )
    assert resp.status_code == 404


def test_list_users_is_paginated(client, make_user, login):
    admin = make_user(Role.ADMIN)
    for _ in range(4):
        make_user()
    resp = client.get("/api/v1/users?page=2&page_size=2", headers=login(admin))
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert len(body["items"]) == 2
    assert client.get("/api/v1/users?page_size=500", headers=login(admin)).status_code == 422
