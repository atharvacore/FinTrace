# Phase 2 Report: Ingestion

Date: 2026-10-11

## Result

| | |
|---|---|
| Tests | **83 passed** on PostgreSQL 16 (36 from Phase 1 + 47 new) |
| Lint | `ruff check` and `ruff format --check` clean for `backend/` and `scripts/` |
| Live smoke test | Uploaded the sample through `POST /imports` with a real server; searched with filters |
| Throughput | 100,000-row CSV through the CLI in 20 s (about 5,000 rows/s on 4 CPUs). Full PaySim (6.36M rows) would take roughly 20 minutes, so the README suggests `--limit` for demos |

## Complete

- **CSV import** (`POST /imports`, `python -m app.cli import-csv`): PaySim header check (missing and unexpected columns listed), per-row Pydantic validation, bad rows reported with their line number and column, good rows still imported, status `completed` / `completed_with_errors` / `failed`, 50 MB API upload cap with a pointer to the CLI, UTF-8 and malformed-file errors, import history (`GET /imports`, `GET /imports/{id}`), audit event per import.
- **Duplicate safety**: deterministic `dedup_key`, `INSERT ... ON CONFLICT DO NOTHING RETURNING`. Re-importing a file inserts 0 rows; duplicates inside one file are counted once.
- **JSON ingestion** (`POST /transactions`): 1–1000 transactions, `external_id` required as an idempotency key, per-item `created` / `duplicate` result, 201 vs 200, audited.
- **Search** (`GET /transactions`): prefix search on accounts and external IDs (LIKE wildcards escaped), type (multi-select), exact account, amount range, date range, source, import batch, four sort orders, pagination with totals, invalid ranges rejected.
- **Detail** (`GET /transactions/{id}`): exposes the ground-truth label only as `synthetic_label_is_fraud`; the list view never shows it.
- **Synthetic sample**: `scripts/generate_sample_data.py` (standard library only) and the committed 5,000-row output in `data/sample/`, with a README saying plainly it is not PaySim and must not be used for reported metrics. A test regenerates it and checks it is byte-identical.

## Incomplete

- `risk_level` and `has_alert` search filters: they need scoring, so they arrive in Phase 4 (not added as do-nothing parameters now).
- Transaction detail does not yet show assessments, alerts or cases (Phases 4–5).

## Blocked

Nothing. PaySim is needed for Phase 3; until it is downloaded, the pipeline will be built and tested on synthetic data, and **no metrics from synthetic data will be presented as results**.

## Bugs found and fixed during this phase

- A non-UTF-8 file crashed with a 500 because the header is read before the error handler was in scope. A test caught it; the handler now wraps header parsing too.
- The transaction detail returned a 500 because the renamed label field could not be read from the database object. Fixed with a validation alias; covered by `test_detail_shows_label_as_synthetic`.
- CORS origins given as a comma-separated environment variable failed to parse (pydantic-settings tries JSON first). Fixed with `NoDecode` and a new test.
- Import was slow (2,000 rows/s). Profiling showed SQLAlchemy recompiling a 1,000-row VALUES clause per chunk; switching to Core `executemany` gave 2.5× speed-up.
- The first generator version assigned random hours and sorted afterwards, which broke account balance continuity. It now simulates hour by hour.

## Commands executed

```bash
python scripts/generate_sample_data.py                       # 5,000 rows, 108 labelled fraud
python -m app.cli import-csv ../data/sample/synthetic_transactions.csv   # twice: 5000 inserted, then 5000 duplicates
python scripts/generate_sample_data.py --rows 100000 --steps 240 --out big.csv
python -m app.cli import-csv big.csv                         # timed, profiled with cProfile
pytest -q                                                    # 83 passed
ruff check . && ruff format --check .                        # backend and scripts
uvicorn app.main:app; curl -F file=@... /api/v1/imports; curl /api/v1/transactions?type=TRANSFER&min_amount=...
```

## Files changed

New: `backend/app/services/ingestion.py`, `backend/app/api/v1/{imports,transactions}.py`, `backend/app/schemas/transaction.py`, `backend/tests/{test_imports,test_transactions,test_sample_data}.py`, `scripts/generate_sample_data.py`, `data/sample/{synthetic_transactions.csv,README.md}`, `docs/phases/PHASE-2.md`.
Modified: `backend/app/api/v1/router.py`, `backend/app/cli.py`, `backend/app/core/config.py`, `backend/pyproject.toml`, `backend/tests/test_config.py`, `.github/workflows/ci.yml`, `README.md`, `docs/CHECKLIST.md`, `docs/DECISIONS.md` (ADR-009 to ADR-012).

## How the code fits together (for interviews)

1. **One validation model, two entry points.** `TransactionIn` validates both CSV rows and API bodies, so the rules cannot drift apart. The API subclass only adds "external_id is required".
2. **Idempotency at the database.** The app computes a `dedup_key`, but the unique index decides. That makes retries and concurrent imports safe without locks: "the database is the source of truth for uniqueness".
3. **Partial success with an exact report.** Imports never fail as a whole because of a few bad lines, and never drop rows silently: `rows_total = inserted + duplicate + rejected` always holds.
4. **Label hygiene.** The fraud label is stored for evaluation, hidden from list views, and named `synthetic_label_is_fraud` where shown, so nobody mistakes it for an investigation outcome. `isFlaggedFraud` is discarded because it would leak a label proxy.
