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
| **Status** | Phases 1–2 complete; Phase 3 pipeline built and tested, real PaySim results pending the dataset. See [docs/CHECKLIST.md](docs/CHECKLIST.md). |
| **Plan** | [docs/PLAN.md](docs/PLAN.md): architecture, schema, API, milestones, risks |
| **Decisions** | [docs/DECISIONS.md](docs/DECISIONS.md) |
| **Stack** | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · scikit-learn · React + TypeScript + Vite |

## What works today (Phases 1 to 3)

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
- A reproducible ML pipeline: data inspection report, leakage-safe features, chronological split,
  logistic-regression baseline and gradient-boosting model, thresholds chosen on validation,
  test metrics focused on analyst workload, and a versioned model artifact.
- 103 automated tests (83 backend on real PostgreSQL, 20 ML), plus ruff linting, all run in
  GitHub Actions.

No model results are published yet: they will come from a PaySim run, never from the synthetic
sample. Scoring, alerts, cases and the React dashboard arrive in Phases 4 and 5.

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
ml/                 Offline training pipeline + shared feature code (see ml/README.md)
data/sample/        Small SYNTHETIC sample (not PaySim); data/raw/ is git-ignored
docs/               Plan, requirements checklist, decisions, phase reports
scripts/            Sample-data generator, database init
.github/workflows/  CI
```

`frontend/` (React dashboard) is added in Phase 5.

## Data

### Getting PaySim

FinTrace's model is trained on **PaySim**, a public **synthetic** mobile-money dataset
(E. A. Lopez-Rojas, A. Elmir and S. Axelsson, "PaySim: A financial mobile money simulator for
fraud detection", EMSS 2016). FinTrace never downloads it for you.

1. Sign in at kaggle.com and open the dataset **"Synthetic Financial Datasets For Fraud
   Detection"** (owner: `ealaxi`; search for "PaySim").
2. Read and accept the licence shown on that page (check it yourself; it has been listed as
   CC BY-SA 4.0).
3. Download and unzip. Move the single CSV (about 470 MB, named like
   `PS_20174392719_1491204439457_log.csv`) to `data/raw/paysim.csv`. `data/raw/` is git-ignored.
4. Check it: the header must be
   `step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud`
   and the file should have about 6.36 million rows.

PaySim fraud labels are **simulated fraud**, not confirmed money laundering.

### Train the model

```bash
pip install -e "./ml[dev]"
python -m fintrace_ml.inspect_data data/raw/paysim.csv --data-kind paysim --out ml/reports
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --promote
```

This writes a versioned artifact under `ml/artifacts/` and copies it to `ml/artifacts/current`,
where the API loads it. See [ml/README.md](ml/README.md) for the method and its leakage
safeguards. Without PaySim you can smoke-test the pipeline on the bundled sample with
`--data-kind synthetic`; every report it produces is stamped "THESE ARE NOT RESULTS".

## Security notes

- `.env` is git-ignored. Only `.env.example`, with placeholders, is committed.
- The API refuses to start without a real `FINTRACE_JWT_SECRET` of 32 or more characters.
- Passwords are hashed with Argon2id and never returned by the API or written to audit events.
- Role checks run on the server for every protected route.
