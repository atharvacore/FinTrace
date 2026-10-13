# Phase 4 Report: Scoring, Rules and Alerts

Date: 2026-10-12 · Delivered as pull request #1 (`wip/phase-4` → `main`)

## Result

| | |
|---|---|
| Tests | **131 backend tests passed** on PostgreSQL 16 (83 earlier + 48 new); 21 ML tests unchanged |
| Lint | `ruff check` and `ruff format --check` clean |
| Online/offline parity | All 5,000 sample transactions: API scores equal the training pipeline's within 1e-5 |
| Real data run | 200,000 PaySim rows (steps 1–13) imported in 63 s and scored with the PaySim model in 2 min 7 s |
| Live smoke test | Logged in, listed alerts, readiness reported the active PaySim model |

## Complete

- **Migration 0002**: `(account, step)` history indexes (replacing two single-column ones), assessment-by-model index, `model_versions.is_synthetic_demo`, `risk_assessments.model_version_id` now NOT NULL, four seeded rules. Upgrade, downgrade and `alembic check` all verified.
- **Model registry** (`/models`, `/models/active`, `/models/sync`, `/models/{id}/activate`, CLI `sync-model`): sha256 verification on register, activate and load; registry copies per version; rollback; audited.
- **Scoring** (`/scoring/transactions/{id}`, `/scoring/run`, CLI `score`): history counts in one SQL query per batch, shared `build_features`, feature-list check against the artifact, rule evaluation, risk level, reason codes (model, rule and indicator codes), at most one open alert per transaction (enforced by a partial unique index since migration 0003, and scoring runs are serialised with a PostgreSQL advisory lock). No model → `503 MODEL_NOT_AVAILABLE` with exact commands.
- **Rules** (`/rules`, `PATCH /rules/{id}`): four types with strict Pydantic parameter schemas (unknown keys rejected), admin-only edits, audited with before/after.
- **Alerts** (`/alerts`, `/alerts/{id}`, `PATCH /alerts/{id}`): filters (status, priority, assignee, unassigned, mine, min score, reason code, transaction), four sort orders, transition table, role rules, row lock against concurrent edits, `closed_at`, audit only on real changes.
- **Transactions**: list shows latest score, level and open-alert flag; filters `risk_level`, `has_open_alert`; detail includes assessment history and alerts.
- Readiness reports the active model (and flags a synthetic one).

## Measured on PaySim (workload, not model quality)

The 200,000 rows scored are the first 13 hours, which are inside the model's **training** period, so this run checks workload and plumbing, not accuracy. Accuracy on unseen hours is in MODEL_REPORT.md.

| Configuration | Alerts | Fraud-labelled transactions alerted | Not alerted |
|---|---:|---:|---:|
| First default rules (`BALANCE_DRAIN` severity high) | 33,000 | 138 of 147 | 9 |
| Shipped defaults (`BALANCE_DRAIN` medium) | **137** | 137 of 147 | 10 |

The model alone raised 137 alerts with zero false positives on these (training-period) rows. `BALANCE_DRAIN` alone fired on 32,978 transactions, because in PaySim 43% of legitimate transfers and cash-outs take the whole balance. It now ships as a medium rule that explains alerts instead of creating them (ADR-021).

## Incomplete

- Cases, notes, decisions, audit-event API and metrics endpoints (Phase 5).
- Alert `case_id` is always null until cases exist (Phase 5).

## Blocked

Nothing.

## Bugs found and fixed during this phase

- The `BALANCE_DRAIN` default would have flooded analysts (see above). Found by running on real PaySim rows, not by unit tests.
- `ARRAY.any()` is deprecated in SQLAlchemy 2.1; the reason-code filter now uses `contains`.
- The Phase 4 branch was cut before the Phase 3 results commit; rebased onto `main` with no conflicts.

## Commands executed

```bash
git rebase main                                   # on wip/phase-4
pytest -q                                         # 131 passed
ruff check . && ruff format --check .
alembic upgrade head && alembic check
python -m app.cli sync-model                      # registered hist-strict-paysim-20261011073433
python -m app.cli import-csv ../data/raw/paysim.csv --limit 200000   # 63 s
python -m app.cli score --limit 200000            # 127 s, run twice (before and after the rule fix)
psql ... (alert breakdown against synthetic labels)
uvicorn app.main:app; curl /auth/login, /alerts, /health/ready
```

## Files changed

New: `backend/alembic/versions/0002_scoring_indexes_and_seed_rules.py`, `backend/app/api/v1/{alerts,models,rules,scoring}.py`, `backend/app/schemas/scoring.py`, `backend/app/services/{alerts,model_registry,rules,scoring}.py`, `backend/tests/{test_models_and_scoring,test_rules,test_alerts}.py`, `docs/phases/PHASE-4.md`.
Modified: `backend/app/api/v1/{health,router,transactions}.py`, `backend/app/{cli.py,core/config.py}`, `backend/app/models/{alert,scoring,transaction}.py`, `backend/app/schemas/transaction.py`, `backend/tests/conftest.py`, `.github/workflows/ci.yml`, `README.md`, `docs/CHECKLIST.md`, `docs/DECISIONS.md` (ADR-018 to ADR-022).

## How the code fits together (for interviews)

1. **One feature function, two data sources.** Training counts history in a DataFrame; the API counts it in PostgreSQL. Everything else is the same function, and a test compares the two on 5,000 transactions. This is how you avoid training/serving skew.
2. **Refuse rather than guess.** No model, or a model whose file hash doesn't match, means a 503 or 409 with instructions, never a made-up score.
3. **Rules and models do different jobs.** The model ranks; rules add explainable context and hard policy limits. The 33,000-vs-137 measurement shows why an alerting rule must be tuned against real volume before it ships.
4. **Workflow rules live on the server.** Who may assign, close or reopen is checked in `services/alerts.py`, with a row lock so two analysts cannot overwrite each other, and every real change is audited with before and after values.

## Priority fix (2026-10-12)

Santa noticed in the Phase 5 screenshots that almost every alert was critical (135 of 137). The
model's scores above its threshold are saturated near 1.0 on PaySim, so "upper half of the band
above the threshold" put nearly every alert in the top band. Critical now requires the model and at
least two monitoring rules to agree (ADR-020). Re-scored, the same rows give 34 critical and 103 high.

## Review fixes (2026-10-12, before Phase 5)

Phases 1–4 were re-checked from a clean clone (fresh venv and database: 131 backend and 21 ML
tests passed, `alembic upgrade` / `downgrade base` / `upgrade` and `alembic check` clean), then
reviewed against the plan. The fixes are listed in [ADR-023](../DECISIONS.md): escalations are
senior-only, one open alert per transaction under concurrency (migration `0003`), upload size
checked before the body is read, model metadata validated, and three smaller error-handling fixes.
12 new tests; **143 backend tests passed**, ruff clean.

