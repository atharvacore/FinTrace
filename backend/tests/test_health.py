def test_liveness_returns_ok_and_request_id(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.headers["X-Request-ID"]


def test_client_request_id_is_echoed(client):
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "trace-123"})
    assert resp.headers["X-Request-ID"] == "trace-123"


def test_unsafe_request_id_is_replaced(client):
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert resp.headers["X-Request-ID"] != "bad id\nwith newline"


def test_readiness_reports_db_migrations_and_missing_model_truthfully(client):
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"]["status"] == "ok"
    assert body["migrations"]["status"] == "ok"
    # No artifact exists in tests: readiness must say so, not pretend.
    assert body["model"]["status"] == "missing"
    assert "Train" in body["model"]["detail"]


def test_unknown_route_uses_consistent_error_shape(client):
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == resp.headers["X-Request-ID"]


def test_unexpected_errors_keep_the_error_shape_and_request_id():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/boom", headers={"X-Request-ID": "req-500"})
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"
    assert resp.json()["error"]["request_id"] == "req-500"
    assert resp.headers["X-Request-ID"] == "req-500"
