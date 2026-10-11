# Phase 1 Report: Foundation

Date: 2026-10-11 · Commit: `c1fc94d` · CI: green (GitHub Actions run 38119907866)

## Result

| | |
|---|---|
| Tests | **36 passed** on PostgreSQL 16, run three times: local server, Docker Compose `db` container, GitHub Actions |
| Lint | `ruff check` clean, `ruff format --check` clean |
| Migrations | `alembic upgrade head` on empty DB ✓, `downgrade base` ✓ (tested), `alembic check`: no drift between models and migration |
| Live smoke test | CLI created an admin, uvicorn served `/docs`, login → `/auth/me` → `/users` all worked |

## Complete

- Repository layout, `.gitignore`, `.gitattributes`, `.env.example` (placeholders only)
- Settings from environment; app refuses to start with a missing or placeholder JWT secret
- Full database schema (11 tables) in one reviewed migration: FKs (`ON DELETE RESTRICT`), CHECK constraints, unique and partial indexes
- Argon2id password hashing, JWT login (`/auth/login` JSON and `/auth/token` for Swagger), `/auth/me`
- Three roles enforced server-side with `require_role`; admin user management with self-lockout protection
- Audit events (with request ID) for user creation, role change, password reset; secrets never logged
- Consistent error body `{error: {code, message, details, request_id}}` for 401/403/404/409/422/500
- `/health` and `/health/ready` (DB, migrations, model artifact reported truthfully)
- `python -m app.cli create-user` (password via prompt or env var, same validation as the API)
- GitHub Actions CI with a PostgreSQL service; Docker Compose `db` service that also creates `fintrace_test`

## Incomplete (planned for later phases)

- Transaction import and API ingestion (Phase 2)
- ML pipeline (Phase 3), scoring, rules and alerts (Phase 4)
- Cases, notes and decisions API, metrics, React dashboard (Phase 5)
- `api` and `web` services in Docker Compose, screenshots, demo script (Phase 6)

## Blocked

Nothing. PaySim is not needed until Phase 3: download it from Kaggle when convenient (see PLAN.md §5).

## Bugs found and fixed during this phase

- Login rejected `admin@fintrace.local` because email validation refuses reserved domains. Login now accepts any string (format rules apply at account creation), and the CLI uses the same validation as the API, so it can no longer create an account the API would reject. Both are covered by tests.
- Alembic autogenerate duplicated the enum CHECK constraints; removed by hand and verified in `pg_constraint`.
- The case-insensitive email index was first written as `lower('email')` (a constant); fixed to `lower(email)` and covered by `test_duplicate_email_is_rejected_case_insensitively`.

## Commands executed

```bash
python3.12 -m venv .venv && pip install -e "backend[dev]"
alembic revision --autogenerate --rev-id 0001 -m "initial schema"
alembic upgrade head && alembic check
pytest -q                               # 36 passed
ruff check . && ruff format --check .   # clean
docker compose up -d --wait             # then pytest against it: 36 passed
python -m app.cli create-user ...; uvicorn app.main:app; curl login, /auth/me, /users
git push; gh run watch                  # CI green
```

## Files changed

`README.md`, `.env.example`, `.gitignore`, `.gitattributes`, `docker-compose.yml`, `.github/workflows/ci.yml`, `scripts/db-init/01-create-test-db.sh`, `docs/CHECKLIST.md`, `docs/DECISIONS.md`, and under `backend/`: `pyproject.toml`, `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial_schema.py`, `app/{__init__,main,db,cli}.py`, `app/core/{config,security,errors,middleware}.py`, `app/api/deps.py`, `app/api/v1/{router,health,auth,users}.py`, `app/models/{base,enums,user,transaction,scoring,alert,case,audit}.py`, `app/schemas/{common,auth,user,health}.py`, `app/services/audit.py`, `tests/{conftest,test_auth,test_config,test_health,test_schema,test_users_rbac}.py`.

## How the code fits together (for interviews)

1. **Request path.** `RequestIdMiddleware` tags each request → the route's dependencies open a DB session (`get_db`), decode the JWT (`get_current_user`) and check the role (`require_role`) → the handler does the work → errors from anywhere are turned into the same JSON shape by `register_error_handlers`.
2. **Why the database enforces rules too.** The API validates input, but constraints like "a closed case must have a decision" and "only one active model" also live in PostgreSQL, so a bug or a manual SQL edit cannot break them. Tests prove the DB rejects bad rows.
3. **Why tests use real migrations.** The test suite builds its schema with `alembic upgrade head`, so a broken migration fails CI, not your demo.
4. **Security choices.** Argon2id hashes, identical 401s for wrong password / unknown email / disabled account, a dummy hash check against timing attacks, and every audit record omits secrets.
