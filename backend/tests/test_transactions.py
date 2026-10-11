import pytest
from sqlalchemy import select

from app.models import AuditEvent
from app.models.enums import Role


def tx(ext_id: str, **overrides) -> dict:
    base = {
        "external_id": ext_id,
        "step": 1,
        "type": "TRANSFER",
        "amount": "100.00",
        "origin_account": "C100",
        "dest_account": "C200",
        "origin_balance_before": "100.00",
        "origin_balance_after": "0.00",
        "dest_balance_before": "0.00",
        "dest_balance_after": "100.00",
    }
    return base | overrides


@pytest.fixture
def senior(make_user, login):
    return login(make_user(Role.SENIOR_ANALYST))


@pytest.fixture
def analyst(make_user, login):
    return login(make_user(Role.ANALYST))


def ingest(client, headers, *items):
    return client.post("/api/v1/transactions", json={"transactions": list(items)}, headers=headers)


def test_api_ingestion_is_idempotent(client, senior):
    first = ingest(client, senior, tx("ext-1"), tx("ext-2", amount="5.50"))
    assert first.status_code == 201
    assert first.json()["inserted"] == 2

    retry = ingest(client, senior, tx("ext-1"), tx("ext-3"))
    assert retry.status_code == 201
    items = retry.json()["items"]
    assert items[0] == {
        "external_id": "ext-1",
        "id": first.json()["items"][0]["id"],
        "status": "duplicate",
    }
    assert items[1]["status"] == "created"

    again = ingest(client, senior, tx("ext-1"))
    assert again.status_code == 200
    assert again.json() | {"items": None} == {"inserted": 0, "duplicates": 1, "items": None}


def test_same_external_id_twice_in_one_request(client, senior):
    body = ingest(client, senior, tx("dup"), tx("dup")).json()
    assert body["inserted"] == 1
    assert [i["status"] for i in body["items"]] == ["created", "duplicate"]
    assert body["items"][0]["id"] == body["items"][1]["id"]


@pytest.mark.parametrize(
    "bad",
    [
        {"amount": "0"},
        {"amount": "1.001"},
        {"type": "WIRE"},
        {"origin_balance_before": "-1"},
        {"origin_account": "has space"},
        {"external_id": ""},
    ],
)
def test_api_ingestion_validates_each_field(client, senior, bad):
    resp = ingest(client, senior, tx("x", **bad))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_api_ingestion_requires_external_id_and_batch_limits(client, senior):
    missing = tx("x")
    del missing["external_id"]
    assert ingest(client, senior, missing).status_code == 422
    assert ingest(client, senior).status_code == 422
    too_many = [tx(f"id-{i}") for i in range(1001)]
    assert ingest(client, senior, *too_many).status_code == 422


def test_analyst_cannot_ingest(client, analyst):
    assert ingest(client, analyst, tx("a")).status_code == 403


def test_ingestion_is_audited(client, senior, db):
    ingest(client, senior, tx("a"), tx("b"))
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "transactions.ingested"))
    assert event.after == {"received": 2, "inserted": 2}


@pytest.fixture
def seeded(client, senior):
    ingest(
        client,
        senior,
        tx("t1", step=1, type="PAYMENT", amount="10.00", origin_account="C1", dest_account="M9"),
        tx("t2", step=2, type="TRANSFER", amount="500.00", origin_account="C2", dest_account="C1"),
        tx("t3", step=3, type="CASH_OUT", amount="2500.00", origin_account="C3", dest_account="C4"),
        tx("t4", step=25, type="TRANSFER", amount="99.99", origin_account="C10", dest_account="C5"),
    )


def ids(resp) -> list[str]:
    assert resp.status_code == 200, resp.text
    return [item["external_id"] for item in resp.json()["items"]]


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["t4", "t3", "t2", "t1"]),
        ("?sort=occurred_at", ["t1", "t2", "t3", "t4"]),
        ("?sort=-amount", ["t3", "t2", "t4", "t1"]),
        ("?type=TRANSFER", ["t4", "t2"]),
        ("?type=TRANSFER&type=PAYMENT", ["t4", "t2", "t1"]),
        ("?account=C1", ["t2", "t1"]),
        ("?q=C1", ["t4", "t2", "t1"]),  # prefix match: C1, C10
        ("?q=t3", ["t3"]),
        ("?min_amount=100&max_amount=1000", ["t2"]),
        ("?from=2026-01-01T01:00:00Z&to=2026-01-01T02:00:00Z", ["t3", "t2"]),
        ("?q=C_", []),  # LIKE wildcards are escaped
    ],
)
def test_search_filters_and_sorting(client, analyst, query, expected):
    assert ids(client.get(f"/api/v1/transactions{query}", headers=analyst)) == expected


@pytest.mark.usefixtures("seeded")
def test_search_pagination_totals(client, analyst):
    body = client.get("/api/v1/transactions?page=2&page_size=3", headers=analyst).json()
    assert body["total"] == 4
    assert len(body["items"]) == 1


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize(
    "query",
    [
        "?min_amount=10&max_amount=5",
        "?from=2026-02-01T00:00:00Z&to=2026-01-01T00:00:00Z",
        "?type=WIRE",
        "?sort=name",
        "?page=0",
    ],
)
def test_search_rejects_invalid_parameters(client, analyst, query):
    resp = client.get(f"/api/v1/transactions{query}", headers=analyst)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_detail_shows_label_as_synthetic(client, senior, analyst):
    created = ingest(client, senior, tx("lab", label_is_fraud=True)).json()["items"][0]
    resp = client.get(f"/api/v1/transactions/{created['id']}", headers=analyst)
    assert resp.status_code == 200
    assert resp.json()["synthetic_label_is_fraud"] is True
    assert client.get("/api/v1/transactions/999999", headers=analyst).status_code == 404


def test_list_hides_label(client, senior, analyst):
    ingest(client, senior, tx("lab", label_is_fraud=True))
    item = client.get("/api/v1/transactions", headers=analyst).json()["items"][0]
    assert "label_is_fraud" not in item and "synthetic_label_is_fraud" not in item
