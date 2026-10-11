import io
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import AuditEvent, Transaction
from app.models.enums import Role

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "data" / "sample" / "synthetic_transactions.csv"

HEADER = (
    "step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,"
    "oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud"
)
GOOD_ROWS = [
    "1,PAYMENT,9839.64,C1231006815,170136.0,160296.36,M1979787155,0.0,0.0,0,0",
    "1,TRANSFER,181.0,C1305486145,181.0,0.0,C553264065,0.0,0.0,1,0",
    "2,CASH_OUT,181.0,C840083671,181.0,0.0,C38997010,21182.0,0.0,1,0",
]


def csv_bytes(*rows: str, header: str = HEADER) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode()


def upload(client, headers, content: bytes, name: str = "tx.csv"):
    return client.post(
        "/api/v1/imports", files={"file": (name, io.BytesIO(content), "text/csv")}, headers=headers
    )


@pytest.fixture
def senior(make_user, login):
    return login(make_user(Role.SENIOR_ANALYST))


def test_valid_csv_is_imported(client, senior, db):
    resp = upload(client, senior, csv_bytes(*GOOD_ROWS))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert (body["rows_total"], body["rows_inserted"], body["rows_duplicate"]) == (3, 3, 0)
    assert body["rows_rejected"] == 0 and body["errors"] == []

    tx = db.scalar(select(Transaction).where(Transaction.origin_account == "C1305486145"))
    assert tx.label_is_fraud is True
    assert str(tx.amount) == "181.00"
    assert tx.occurred_at.isoformat() == "2026-01-01T00:00:00+00:00"  # step 1 -> epoch


def test_reimporting_same_file_inserts_nothing(client, senior, db):
    content = csv_bytes(*GOOD_ROWS)
    upload(client, senior, content)
    second = upload(client, senior, content).json()
    assert (second["rows_inserted"], second["rows_duplicate"]) == (0, 3)
    assert db.scalar(select(func.count()).select_from(Transaction)) == 3


def test_duplicate_rows_within_one_file_are_counted_once(client, senior):
    body = upload(client, senior, csv_bytes(GOOD_ROWS[0], GOOD_ROWS[0])).json()
    assert (body["rows_inserted"], body["rows_duplicate"]) == (1, 1)


def test_bad_rows_are_reported_and_good_rows_still_imported(client, senior):
    rows = [
        GOOD_ROWS[0],
        "1,WIRE,10.0,C1,10.0,0.0,C2,0.0,0.0,0,0",  # line 3: unknown type
        "1,PAYMENT,-5,C1,10.0,0.0,M2,0.0,0.0,0,0",  # line 4: negative amount
        "1,PAYMENT,abc,C1,10.0,0.0,M2,0.0,0.0,0,0",  # line 5: not a number
        "1,PAYMENT,5.0,C1,10.0,5.0,M2,0.0,0.0,maybe,0",  # line 6: bad label
        "1,PAYMENT,5.0,C1",  # line 7: too few columns
        "x,PAYMENT,5.0,C 1,10.0,5.0,M2,0.0,0.0,0,0",  # line 8: bad step and account
        GOOD_ROWS[1],
    ]
    body = upload(client, senior, csv_bytes(*rows)).json()
    assert body["status"] == "completed_with_errors"
    assert (body["rows_total"], body["rows_inserted"], body["rows_rejected"]) == (8, 2, 6)
    by_line = {e["row"]: " ".join(e["errors"]) for e in body["errors"]}
    assert sorted(by_line) == [3, 4, 5, 6, 7, 8]
    assert "type" in by_line[3]
    assert by_line[4].startswith("amount")
    assert "isFraud" in by_line[6]
    assert "columns" in by_line[7]
    assert "step" in by_line[8] and "nameOrig" in by_line[8]
    assert body["errors_truncated"] is False


def test_all_rows_bad_marks_import_failed(client, senior):
    body = upload(client, senior, csv_bytes("1,WIRE,10,C1,10,0,C2,0,0,0,0")).json()
    assert body["status"] == "failed"


def test_many_errors_are_capped_but_counted(client, senior):
    bad = ["1,WIRE,10,C1,10,0,C2,0,0,0,0"] * 150
    body = upload(client, senior, csv_bytes(*bad)).json()
    assert body["rows_rejected"] == 150
    assert len(body["errors"]) == 100
    assert body["errors_truncated"] is True


@pytest.mark.parametrize(
    ("content", "name", "expected"),
    [
        (b"", "tx.csv", "empty"),
        (csv_bytes(GOOD_ROWS[0], header=HEADER.replace("amount", "amt")), "tx.csv", "header"),
        (csv_bytes(*GOOD_ROWS), "tx.xlsx", ".csv"),
        (b"\xff\xfe\x00bad", "tx.csv", "UTF-8"),
    ],
)
def test_unusable_files_are_rejected_with_clear_message(client, senior, content, name, expected):
    resp = upload(client, senior, content, name)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CSV"
    assert expected in resp.json()["error"]["message"]


def test_header_error_lists_missing_and_unexpected_columns(client, senior):
    resp = upload(client, senior, csv_bytes(header=HEADER.replace("amount", "amt")))
    details = {d["field"]: d["message"] for d in resp.json()["error"]["details"]}
    assert details == {"amount": "required column is missing", "amt": "unexpected column"}


def test_upload_size_limit(client, senior, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    big = csv_bytes(*([GOOD_ROWS[0]] * 20_000))
    assert len(big) > 1024 * 1024
    resp = upload(client, senior, big)
    assert resp.status_code == 413
    assert "import-csv" in resp.json()["error"]["message"]


def test_analyst_cannot_import(client, make_user, login):
    resp = upload(client, login(make_user(Role.ANALYST)), csv_bytes(*GOOD_ROWS))
    assert resp.status_code == 403


def test_import_is_audited_and_listed(client, senior, make_user, login, db):
    batch = upload(client, senior, csv_bytes(*GOOD_ROWS)).json()
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "import.completed"))
    assert event.entity_id == str(batch["id"])
    assert event.after["rows_inserted"] == 3

    analyst = login(make_user(Role.ANALYST))
    listing = client.get("/api/v1/imports", headers=analyst).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == batch["id"]
    assert client.get(f"/api/v1/imports/{batch['id']}", headers=analyst).status_code == 200
    assert client.get("/api/v1/imports/999", headers=analyst).status_code == 404


def test_bundled_synthetic_sample_imports_cleanly(client, senior):
    body = upload(client, senior, SAMPLE.read_bytes(), SAMPLE.name).json()
    assert body["status"] == "completed"
    assert body["rows_total"] == body["rows_inserted"] == 5000
