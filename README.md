# FinTrace

**Intelligent Financial Crime Detection & Investigation Platform — a portfolio prototype.**

FinTrace imports transactions, scores them with configurable monitoring rules and a supervised
model, raises alerts for human review, and gives analysts an investigation workflow with a full
audit trail.

> ⚠️ **Responsible use.** FinTrace is a learning and portfolio project. It is **not**
> production-ready, **not** regulatory-certified, and **not** validated for real anti-money-laundering
> decisions. It uses synthetic data only. Risk scores are triage signals for a human reviewer,
> never proof of wrongdoing.

| | |
|---|---|
| **Status** | Phase 2 of 6 complete (foundation, ingestion). See [docs/CHECKLIST.md](docs/CHECKLIST.md). |
| **Plan** | [docs/PLAN.md](docs/PLAN.md): architecture, schema, API, milestones, risks |
| **Decisions** | [docs/DECISIONS.md](docs/DECISIONS.md) |
| **Stack** | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · scikit-learn · React + TypeScript + Vite |

## What works today (Phases 1 and 2)

- FastAPI backend with versioned routes under `/api/v1` and interactive docs at `/docs`.
- Full database schema (users, imports, transactions, rules, model versions, risk assessments,
  alerts, cases, notes, audit events) created by an Alembic migration, with foreign keys,
  CHECK constraints and indexes.
- Login with Argon2-hashed passwords and JWT access tokens.
- Three roles (`analyst` < `senior_analyst` < `admin`) enforced on the server.
- Audit events for user creation, role changes and password resets.
- Consistent JSON errors with a request ID, and health and readiness endpoints that report the
  database, migration and model status truthfully.
- CSV import in the PaySim format: every row validated, bad rows reported with their line number,
  duplicates skipped (re-importing a file inserts nothing), import history kept.
- JSON ingestion API, idempotent by `external_id`, and transaction search with filters, sorting and
  pagination.
- A clearly labelled **synthetic** sample file (`data/sample/`) and the script that generates it.
- 83 automated tests against a real PostgreSQL database, plus ruff linting, both run in GitHub Actions.

The ML pipeline, scoring, alerts, cases and the React dashboard arrive in Phases 3 to 5.

## Quick start

You need **Python 3.12**, **Git**, and either **Docker Desktop** (easiest) or a local
**PostgreSQL 16**.

### 1. Clone and configure

PowerShell (Windows):

```powershell
git clone https://github.com/atharvacore/FinTrace.git
cd FinTrace
Copy-Item .env.example .env
# Generate a JWT secret and paste it into .env as FINTRACE_JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

bash (macOS / Linux):

```bash
git clone https://github.com/atharvacore/FinTrace.git
cd FinTrace
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into .env
```

Then open `.env` and replace every `CHANGE_ME`. Use the same password in `POSTGRES_PASSWORD` and
inside `FINTRACE_DATABASE_URL`.

### 2. Start the database

```bash
docker compose up -d --wait db
```

This also creates a second database, `fintrace_test`, for the automated tests. If port 5432 is
taken, set `POSTGRES_PORT` in `.env` and use that port in `FINTRACE_DATABASE_URL`.

### 3. Install the backend

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".\backend[dev]"
```

bash:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e "./backend[dev]"
```

### 4. Apply migrations and create your first admin

Run these from the `backend` folder with the virtual environment active.

PowerShell:

```powershell
cd backend
alembic upgrade head
$env:FINTRACE_NEW_USER_PASSWORD = "choose-a-long-password"
python -m app.cli create-user --email admin@example.com --name "Admin" --role admin
Remove-Item Env:FINTRACE_NEW_USER_PASSWORD
```

bash:

```bash
cd backend
alembic upgrade head
python -m app.cli create-user --email admin@example.com --name "Admin" --role admin
# (prompts for the password; or set FINTRACE_NEW_USER_PASSWORD for one command)
```

Passwords must be at least 12 characters.

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs, click **Authorize**, and sign in with the admin email and
password. `GET /api/v1/health/ready` shows whether the database, migrations and model artifact
are in place.

### 6. Import the synthetic sample

From the `backend` folder:

```bash
python -m app.cli import-csv ../data/sample/synthetic_transactions.csv
```

Run it a second time and it reports 5,000 duplicates and inserts nothing. You can also upload a CSV
through `POST /api/v1/imports` in the Swagger UI (senior analyst or admin, 50 MB limit). For the
full PaySim file, the command line streams from disk at roughly 5,000 rows per second on a
4-core machine, so use `--limit 200000` for a quicker demo database.

To regenerate the sample (or make a bigger one for experiments):

```bash
python ../scripts/generate_sample_data.py --rows 5000 --seed 42 --out ../data/sample/synthetic_transactions.csv
```

### 7. Run the tests and linters

The tests need the `fintrace_test` database. They **drop and recreate** its schema, so never
point them at a database you care about.

PowerShell:

```powershell
cd backend
$env:FINTRACE_TEST_DATABASE_URL = "postgresql+psycopg://fintrace:YOUR_PASSWORD@localhost:5432/fintrace_test"
pytest
ruff check .
ruff format --check .
```

bash:

```bash
cd backend
export FINTRACE_TEST_DATABASE_URL="postgresql+psycopg://fintrace:YOUR_PASSWORD@localhost:5432/fintrace_test"
pytest && ruff check . && ruff format --check .
```

## Repository layout

```
backend/            FastAPI app, SQLAlchemy models, Alembic migrations, tests
  app/api/v1/       Route handlers (health, auth, users, transactions, imports)
  app/core/         Settings, security, errors, middleware
  app/models/       Database tables
  app/schemas/      Request and response models (Pydantic)
  app/services/     Business logic (audit trail; more per phase)
  alembic/          Database migrations
  tests/            pytest suite (runs against real PostgreSQL)
data/sample/        Small SYNTHETIC sample (not PaySim); data/raw/ is git-ignored
docs/               Plan, requirements checklist, decisions, phase reports
scripts/            Sample-data generator, database init
.github/workflows/  CI
```

`ml/` (training pipeline) and `frontend/` (React dashboard) are added in Phases 3 and 5.

## Data

FinTrace's model is trained on **PaySim**, a public **synthetic** mobile-money dataset. It is
never downloaded automatically. Instructions for obtaining it are in
[docs/PLAN.md §5](docs/PLAN.md#5-dependency-and-environment-plan) and will move here in Phase 3.
PaySim fraud labels are simulated fraud, not confirmed money laundering.

## Security notes

- `.env` is git-ignored. Only `.env.example`, with placeholders, is committed.
- The API refuses to start without a real `FINTRACE_JWT_SECRET` of 32 or more characters.
- Passwords are hashed with Argon2id and never returned by the API or written to audit events.
- Role checks run on the server for every protected route.
