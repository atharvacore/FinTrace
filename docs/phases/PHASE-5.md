# Phase 5 Report: Investigations and Dashboard

Date: 2026-10-12 · Branch `wip/phase-5` (built on Phase 4, pull request #1)

## Result

| | |
|---|---|
| Backend tests | **166 passed** on PostgreSQL 16 (143 after the review fixes + 23 new) |
| ML tests | 21 passed (unchanged) |
| Frontend | `npm run typecheck`, `npm run lint`, `npm test` (**13 passed**) and `npm run build` all clean |
| Lint | `ruff check` and `ruff format --check` clean (backend, ml, scripts) |
| Click-through | Scripted Chromium walk-through against the 200,000-row PaySim database as an analyst and a senior analyst: 15 steps, no console errors, no failed API calls, no horizontal scroll at phone width, dark mode renders |
| Speed on 200k rows | Overview metrics 0.59 s, risk distribution 0.65 s, alert and case lists under 0.04 s |

## Complete

### Backend
- **Cases** (`/cases`): create (optionally linking alerts), list with filters (status, priority, assignee, mine, unassigned, search by reference or title) and counts, detail with alerts, notes and the case's audit timeline, `PATCH` for title, description, status, priority and assignee.
- **Case rules** (enforced on the server, ADR-024): analysts work cases assigned to them and can only assign themselves; working an unassigned case takes it; seniors work and assign any case. Status moves between open, investigating and pending decision; only a senior closes a case, by recording a decision with a written rationale. A closed case is final (409 `CASE_CLOSED`) but still accepts notes.
- **Alert links**: an alert belongs to at most one case (unique constraint plus `409 ALERT_ALREADY_IN_CASE`); link and unlink are audited. Alerts and transactions now show their case.
- **Notes**: append-only, any analyst, no edit or delete endpoint.
- **Audit API** (`/audit-events`, senior analyst): filter by record type and ID, actor, action (exact or prefix like `case.`) and time; newest first.
- **Metrics**: `/metrics/overview` (counts, workload, alerts per 1,000 scored, cases and decisions, the user's own work, alerts against the synthetic labels), `/metrics/risk-distribution` (latest score per transaction, so re-scoring does not double count), `/metrics/model-evaluation` (stored offline metrics plus caveats generated from them).
- `GET /users/assignable` (analyst) lists active people by name and role only, for assignment dropdowns.

### Frontend (`frontend/`, React 19 + TypeScript + Vite)
- Pages: login, overview, alert queue, alert detail, cases, case detail, transactions, transaction detail, model evaluation, rules, audit log (senior only).
- Every button calls the API: assign, status changes, open a case from selected alerts, add to an existing case, link and unlink alerts, notes, decisions, score a transaction (senior), edit rules (admin).
- Synthetic-data banner on every page; dataset labels shown only as "synthetic label"; the model page leads with its caveats.
- Loading, empty and error states on every page; errors show the API message and request ID with a retry button.
- Types are generated from the API's OpenAPI schema (`scripts/export_openapi.py`, `npm run gen:api`); CI fails if either is out of date.
- Filters live in the URL, so a filtered view can be reloaded or shared. Light and dark themes; usable at phone width.

## Incomplete

- Docker Compose services for the API and web app, seed/demo script, committed screenshots, resume bullets and the final limitations write-up (Phase 6).
- No user-management page: admins use the CLI or Swagger UI (`/users`).
- No CSV upload page: imports use the CLI or Swagger UI (`POST /imports`).

## Blocked

Nothing.

## Bugs found and fixed during this phase

- Before Phase 5, a clean-clone re-check and code review of Phases 1–4 found an escalation bypass, a duplicate-alert race, a late upload-size check and smaller issues. Fixed on pull request #1 (ADR-023, migration 0003).
- `DISTINCT ON` via `select().distinct(col)` is deprecated in SQLAlchemy 2.1; the latest-assessment query uses `row_number()` instead.
- ESLint flagged a `setState` inside an effect on the transactions page; replaced with state adjusted during render.

## Commands executed

```bash
# Re-check of Phases 1–4 from a fresh clone and virtual environment
alembic upgrade head && alembic downgrade base && alembic upgrade head && alembic check
pytest -q                                      # backend 131 passed, ml 21 passed (before fixes)

# Phase 5
pytest -q                                      # backend: 166 passed
cd ../ml && pytest -q                          # 21 passed
python scripts/export_openapi.py               # writes frontend/openapi.json
cd frontend && npm ci && npm run gen:api && npm run typecheck && npm run lint && npm test && npm run build
uvicorn app.main:app --port 8000 & npm run dev  # then a scripted Chromium walk-through (not committed; Phase 6 adds the screenshot script)
```

## How the code fits together

- `backend/app/services/cases.py` holds the case rules; `backend/app/api/v1/cases.py` is thin routing that locks the case row (`SELECT … FOR UPDATE`), applies a rule, writes the audit event in the same transaction and returns the refreshed detail.
- `backend/app/api/v1/metrics.py` computes everything from the database at request time. The risk distribution uses the latest assessment per transaction for the active model and buckets scores in SQL.
- `frontend/src/api/client.ts` wraps `fetch` and turns the API's error body into an `ApiError`. Pages use TanStack Query for loading, caching and refetching after changes.
- `frontend/src/lib/roles.ts` mirrors the server's alert rules only to hide buttons; the server stays the authority.
