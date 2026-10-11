from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.models.enums import Role
from tests.conftest import TEST_PASSWORD


def test_login_returns_bearer_token(client, make_user):
    user = make_user(Role.ANALYST)
    resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_minutes * 60


def test_login_email_is_case_insensitive(client, make_user):
    user = make_user(email="Mixed.Case@Example.com")
    resp = client.post(
        "/api/v1/auth/login", json={"email": "mixed.case@example.com", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, user


def test_wrong_password_unknown_email_and_inactive_user_all_get_same_401(client, make_user):
    active = make_user()
    inactive = make_user(is_active=False)
    attempts = [
        {"email": active.email, "password": "wrong-password-123"},
        {"email": "nobody@example.com", "password": TEST_PASSWORD},
        {"email": inactive.email, "password": TEST_PASSWORD},
    ]
    for attempt in attempts:
        resp = client.post("/api/v1/auth/login", json=attempt)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_oauth2_token_endpoint_for_swagger(client, make_user):
    user = make_user()
    resp = client.post(
        "/api/v1/auth/token", data={"username": user.email, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_returns_user_without_password_hash(client, make_user, login):
    user = make_user(Role.SENIOR_ANALYST)
    resp = client.get("/api/v1/auth/me", headers=login(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user.email
    assert body["role"] == "senior_analyst"
    assert "password" not in str(body).lower()


def test_password_is_stored_as_argon2_hash(make_user):
    user = make_user()
    assert user.password_hash.startswith("$argon2id$")
    assert TEST_PASSWORD not in user.password_hash


def test_tampered_and_expired_tokens_are_rejected(client, make_user):
    user = make_user()
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "typ": "access",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    forged = jwt.encode(
        {
            "sub": str(user.id),
            "typ": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "a-different-secret-that-is-long-enough-to-sign",
        algorithm="HS256",
    )
    for token in (expired, forged, "not-a-jwt"):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


def test_token_of_deactivated_user_stops_working(client, make_user, login, db):
    user = make_user()
    headers = login(user)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_cli_creates_user_that_can_log_in(client):
    from app.cli import create_user

    create_user("cli.admin@example.com", "CLI Admin", Role.ADMIN, "cli-password-long-enough")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "cli.admin@example.com", "password": "cli-password-long-enough"},
    )
    assert resp.status_code == 200


def test_cli_rejects_what_the_api_would_reject():
    import pytest

    from app.cli import create_user

    with pytest.raises(SystemExit, match="Invalid user details"):
        create_user("admin@fintrace.local", "Bad", Role.ADMIN, "cli-password-long-enough")
    with pytest.raises(SystemExit, match="password"):
        create_user("ok@example.com", "Bad", Role.ADMIN, "short")
