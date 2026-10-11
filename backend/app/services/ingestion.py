"""Validated, duplicate-safe transaction ingestion (CSV files and the JSON API).

Duplicate safety: every transaction gets a `dedup_key`. Inserts use
`INSERT ... ON CONFLICT (dedup_key) DO NOTHING RETURNING id`, so re-importing a file or
retrying an API call never creates a second copy, and the database (not application code)
is the final guard.
"""

import csv
import hashlib
import io
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import BinaryIO

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import ImportBatch, Transaction, User
from app.models.enums import ImportStatus, TransactionSource
from app.schemas.transaction import TransactionIn

# PaySim "step" is an hour index. We map it onto a fixed, clearly synthetic calendar so the UI
# can show dates: step 1 -> 2026-01-01 00:00 UTC, step 2 -> 01:00, and so on.
SIMULATION_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

# PaySim column -> our field. `isFlaggedFraud` is deliberately ignored: it is the output of
# PaySim's own toy rule, not ground truth, and using it as a feature would leak a label proxy.
PAYSIM_COLUMNS = {
    "step": "step",
    "type": "type",
    "amount": "amount",
    "nameOrig": "origin_account",
    "oldbalanceOrg": "origin_balance_before",
    "newbalanceOrig": "origin_balance_after",
    "nameDest": "dest_account",
    "oldbalanceDest": "dest_balance_before",
    "newbalanceDest": "dest_balance_after",
}
OPTIONAL_COLUMNS = {"isFraud": "label_is_fraud", "external_id": "external_id"}
IGNORED_COLUMNS = {"isFlaggedFraud"}

MAX_STORED_ERRORS = 100
CHUNK_SIZE = 1000


def occurred_at_for_step(step: int) -> datetime:
    return SIMULATION_EPOCH + timedelta(hours=max(step - 1, 0))


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def dedup_key_for(tx: TransactionIn) -> str:
    """Stable identity of a transaction.

    With an external_id (API clients), the ID alone is the identity. Without one (PaySim has no
    transaction ID), we hash every business field. Two genuinely identical PaySim rows would be
    treated as one; with amounts and four balances to the cent this is vanishingly rare, and the
    trade-off is documented in docs/DECISIONS.md.
    """
    if tx.external_id:
        material = f"ext|{tx.external_id}"
    else:
        material = "|".join(
            [
                "row",
                str(tx.step),
                tx.type.value,
                _money(tx.amount),
                tx.origin_account,
                _money(tx.origin_balance_before),
                _money(tx.origin_balance_after),
                tx.dest_account,
                _money(tx.dest_balance_before),
                _money(tx.dest_balance_after),
            ]
        )
    return hashlib.sha256(material.encode()).hexdigest()


def _to_row(tx: TransactionIn, source: TransactionSource, batch_id: int | None) -> dict:
    return {
        "dedup_key": dedup_key_for(tx),
        "external_id": tx.external_id,
        "source": source,
        "import_batch_id": batch_id,
        "step": tx.step,
        "occurred_at": occurred_at_for_step(tx.step),
        "type": tx.type,
        "amount": tx.amount,
        "origin_account": tx.origin_account,
        "dest_account": tx.dest_account,
        "origin_balance_before": tx.origin_balance_before,
        "origin_balance_after": tx.origin_balance_after,
        "dest_balance_before": tx.dest_balance_before,
        "dest_balance_after": tx.dest_balance_after,
        "label_is_fraud": tx.label_is_fraud,
    }


_INSERT_RETURNING_KEY = (
    insert(Transaction.__table__)
    .on_conflict_do_nothing(index_elements=["dedup_key"])
    .returning(Transaction.__table__.c.dedup_key)
)


def insert_ignoring_duplicates(db: Session, rows: list[dict]) -> int:
    """Insert rows; return how many were actually new."""
    if not rows:
        return 0
    # Core executemany: SQLAlchemy batches it with "insertmanyvalues" and compiles the statement
    # once, which is far faster than compiling a 1000-row VALUES clause per chunk.
    return len(db.connection().execute(_INSERT_RETURNING_KEY, rows).all())


# ---------------------------------------------------------------- CSV import


@dataclass
class CsvImportResult:
    rows_total: int = 0
    rows_inserted: int = 0
    rows_duplicate: int = 0
    rows_rejected: int = 0
    errors: list[dict] = field(default_factory=list)

    def reject(self, line: int, messages: list[str]) -> None:
        self.rows_rejected += 1
        if len(self.errors) < MAX_STORED_ERRORS:
            self.errors.append({"row": line, "errors": messages})


def _format_validation_error(exc: ValidationError) -> list[str]:
    reverse = {v: k for k, v in {**PAYSIM_COLUMNS, **OPTIONAL_COLUMNS}.items()}
    messages = []
    for err in exc.errors():
        name = str(err["loc"][0]) if err["loc"] else "row"
        messages.append(f"{reverse.get(name, name)}: {err['msg']}")
    return messages


def _parse_label(raw: str) -> bool | None | str:
    value = raw.strip()
    if value == "":
        return None
    if value in {"0", "1"}:
        return value == "1"
    return raw  # let Pydantic report the bad value


def _iter_valid_rows(reader: csv.DictReader, result: CsvImportResult) -> Iterator[TransactionIn]:
    for row in reader:
        line = reader.line_num
        result.rows_total += 1
        if None in row or any(v is None for v in row.values()):
            result.reject(line, ["row has a different number of columns than the header"])
            continue
        data = {ours: row[theirs].strip() for theirs, ours in PAYSIM_COLUMNS.items()}
        if "isFraud" in row:
            data["label_is_fraud"] = _parse_label(row["isFraud"])
        if "external_id" in row and row["external_id"].strip():
            data["external_id"] = row["external_id"].strip()
        try:
            yield TransactionIn.model_validate(data)
        except ValidationError as exc:
            result.reject(line, _format_validation_error(exc))


def _check_header(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise AppError(422, "INVALID_CSV", "The file is empty or has no header row")
    names = set(fieldnames)
    missing = sorted(set(PAYSIM_COLUMNS) - names)
    unknown = sorted(names - set(PAYSIM_COLUMNS) - set(OPTIONAL_COLUMNS) - IGNORED_COLUMNS)
    if missing or unknown:
        details = [{"field": c, "message": "required column is missing"} for c in missing]
        details += [{"field": c, "message": "unexpected column"} for c in unknown]
        raise AppError(
            422,
            "INVALID_CSV",
            "CSV header does not match the PaySim format. Expected columns: "
            + ", ".join([*PAYSIM_COLUMNS, *OPTIONAL_COLUMNS, *IGNORED_COLUMNS]),
            details,
        )


def _import_rows(
    db: Session,
    reader: csv.DictReader,
    filename: str,
    file_sha256: str,
    uploaded_by: User | None,
    limit: int | None,
) -> tuple[ImportBatch, CsvImportResult]:
    _check_header(reader.fieldnames)
    batch = ImportBatch(
        filename=filename[-255:],
        file_sha256=file_sha256,
        uploaded_by_id=uploaded_by.id if uploaded_by else None,
        status=ImportStatus.COMPLETED,
    )
    db.add(batch)
    db.flush()

    result = CsvImportResult()
    pending: list[dict] = []
    for tx in _iter_valid_rows(reader, result):
        pending.append(_to_row(tx, TransactionSource.CSV, batch.id))
        if len(pending) >= CHUNK_SIZE:
            result.rows_inserted += insert_ignoring_duplicates(db, pending)
            pending.clear()
        if limit is not None and result.rows_total >= limit:
            break
    result.rows_inserted += insert_ignoring_duplicates(db, pending)
    return batch, result


def import_csv(
    db: Session,
    file: BinaryIO,
    filename: str,
    uploaded_by: User | None,
    limit: int | None = None,
) -> ImportBatch:
    """Validate and import a PaySim-format CSV. Commits nothing; the caller commits."""
    digest = hashlib.sha256()
    for chunk in iter(lambda: file.read(1024 * 1024), b""):
        digest.update(chunk)
    file.seek(0)

    text = io.TextIOWrapper(file, encoding="utf-8-sig", newline="")
    try:
        batch, result = _import_rows(
            db, csv.DictReader(text), filename, digest.hexdigest(), uploaded_by, limit
        )
    except UnicodeDecodeError:
        raise AppError(422, "INVALID_CSV", "The file is not valid UTF-8 text") from None
    except csv.Error as exc:
        raise AppError(422, "INVALID_CSV", f"Malformed CSV: {exc}") from None
    finally:
        text.detach()  # leave the caller's file open

    valid = result.rows_total - result.rows_rejected
    result.rows_duplicate = valid - result.rows_inserted
    batch.rows_total = result.rows_total
    batch.rows_inserted = result.rows_inserted
    batch.rows_duplicate = result.rows_duplicate
    batch.rows_rejected = result.rows_rejected
    batch.errors = result.errors
    if result.rows_total > 0 and result.rows_rejected == result.rows_total:
        batch.status = ImportStatus.FAILED
    elif result.rows_rejected:
        batch.status = ImportStatus.COMPLETED_WITH_ERRORS
    return batch


# ---------------------------------------------------------------- API ingestion


def ingest_api_transactions(
    db: Session, transactions: Iterable[TransactionIn]
) -> tuple[int, list[tuple[str, int, bool]]]:
    """Insert API transactions idempotently.

    Returns (inserted_count, [(external_id, id, created)]) in request order.
    """
    txs = list(transactions)
    rows = [_to_row(tx, TransactionSource.API, None) for tx in txs]
    created_keys = set(db.connection().execute(_INSERT_RETURNING_KEY, rows).scalars().all())

    keys = [row["dedup_key"] for row in rows]
    ids = {
        key: tx_id
        for key, tx_id in db.execute(
            select(Transaction.dedup_key, Transaction.id).where(Transaction.dedup_key.in_(keys))
        )
    }

    results = []
    seen: set[str] = set()
    for tx, key in zip(txs, keys, strict=True):
        created = key in created_keys and key not in seen
        seen.add(key)
        results.append((tx.external_id or "", ids[key], created))
    return len(created_keys), results
