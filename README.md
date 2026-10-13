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
| **Status** | All six phases complete: foundation, ingestion, ML with measured PaySim results, scoring and alerts, investigations and dashboard, packaging and demo. See [docs/CHECKLIST.md](docs/CHECKLIST.md). |
| **Plan** | [docs/PLAN.md](docs/PLAN.md): architecture, schema, API, milestones, risks |
| **Decisions** | [docs/DECISIONS.md](docs/DECISIONS.md) |
| **Read next** | [Architecture](docs/ARCHITECTURE.md) · [Model report](docs/MODEL_REPORT.md) · [Known limitations](docs/LIMITATIONS.md) · [Demo script](docs/DEMO.md) |
| **Stack** | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · scikit-learn · React + TypeScript + Vite |

## Screenshots

| | |
|---|---|
| ![Overview](docs/screenshots/02-overview.png) | ![Alert detail](docs/screenshots/04-alert-detail.png) |
| ![Case](docs/screenshots/05-case.png) | ![Sign in](docs/screenshots/01-login.png) |

More in [docs/screenshots/](docs/screenshots/), taken from 200,000 PaySim transactions scored by
the PaySim model. Regenerate them with `npm run screenshots` in `frontend` (see the script's header).

## What works today

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
- Measured results on the full PaySim dataset, with an honest explanation of why they are so high
  (a simulator signature) and a diagnostic run without it: [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md).
- Online scoring with the trained model plus four configurable monitoring rules. Each risk
  assessment stores the model version, time, score, level, reason codes and rule hits. A test
  proves the API's scores equal the training pipeline's on 5,000 transactions.
- A model registry: register, verify (sha256) and switch model versions. With no model, scoring
  returns `503 MODEL_NOT_AVAILABLE` with the commands to fix it, instead of inventing a score.
- An alert queue with filters, sorting, assignment and a status workflow enforced on the server
  (analysts work their own alerts; senior analysts assign, close escalations and reopen).
- Investigation cases: open a case from alerts, assign it, move it through its statuses, add
  append-only notes, and have a senior analyst close it with a decision and written rationale.
  Every change appears in the case timeline and the audit log.
- An audit-log API for senior analysts, and dashboard metrics computed from the database.
- A React dashboard: overview, alert queue, cases, transactions, model evaluation (caveats first),
  rules and audit log, with loading, empty and error states and a synthetic-data banner on every page.
  It has its own look (an investigator's ledger: dark ink by default, a light paper theme, serif
  headlines, monospaced figures, one heat scale for risk) and self-hosted fonts.
- Alert priority that reflects agreement: **critical** only when the model and at least two
  monitoring rules agree (ADR-020).
- Admin screens: an **Imports** page (upload a CSV, see each import's inserted, duplicate and
  rejected rows with line-level problems, score new transactions) and a **Users** page for admins
  (create accounts, change roles, deactivate, reset passwords; admins cannot lock themselves out).
- One-command local stack: Docker Compose runs PostgreSQL, the API (non-root, migrations on start)
  and the web app (nginx with security headers), and `demo-seed` loads demo users, data, a model
  and an example case.
- 209 automated tests (169 backend on real PostgreSQL, 21 ML, 19 frontend), plus ruff, ESLint and
  TypeScript checks, all run in GitHub Actions, and a CI job that builds the Compose stack, seeds it
  and checks it through the web proxy.

## Quick start with Docker (recommended)

You need **Git** and **Docker Desktop**.

PowerShell (Windows):

```powershell
git clone https://github.com/atharvacore/FinTrace.git
cd FinTrace
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into .env as FINTRACE_JWT_SECRET
```

bash:

```bash
git clone https://github.com/atharvacore/FinTrace.git && cd FinTrace
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"  # paste into .env as FINTRACE_JWT_SECRET
```

In `.env`, also set `POSTGRES_PASSWORD` and `FINTRACE_DEMO_PASSWORD` (12+ characters, local demo
only). Then, in either shell:

```bash
docker compose up -d --build --wait
docker compose exec api python -m app.cli demo-seed
```

Open http://localhost:8080 and sign in as `demo.analyst@example.com` or `demo.senior@example.com`
with your `FINTRACE_DEMO_PASSWORD`. [docs/DEMO.md](docs/DEMO.md) is a five-minute walk-through.

Without a PaySim model, `demo-seed` trains a **synthetic smoke-test model** on the bundled sample,
and the dashboard labels it as such. To show real PaySim scores, train on PaySim first
(["Train the model"](#train-the-model)), then copy the model into the stack:

```bash
docker compose cp ml/artifacts/current api:/app/ml/artifacts/
docker compose exec api python -m app.cli sync-model
```

If ports 5432, 8000 or 8080 are taken, change `POSTGRES_PORT`, `API_PORT` or `WEB_PORT` in `.env`.
`docker compose down -v` stops everything and deletes the data.

## Quick start for development

For working on the code you run the API and the dashboard on your machine. You need
**Python 3.12**, **Node.js 22**, **Git**, and either **Docker Desktop** (for the database) or a local
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
pip install -e .\ml -e ".\backend[dev]"
```

bash:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ./ml -e "./backend[dev]"
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
on the dashboard's **Imports** page (senior analyst or admin, 50 MB limit), which lists rejected
rows by line number and can score the new transactions. For the
full PaySim file, the command line streams from disk at roughly 5,000 rows per second on a
4-core machine, so use `--limit 200000` for a quicker demo database.

To regenerate the sample (or make a bigger one for experiments):

```bash
python ../scripts/generate_sample_data.py --rows 5000 --seed 42 --out ../data/sample/synthetic_transactions.csv
```

### 7. Register a model and score

After training (see "Train the model" below), from the `backend` folder:

```bash
python -m app.cli sync-model            # verify, register and activate ml/artifacts/current
python -m app.cli score --limit 200000  # score transactions the active model has not seen
```

Or, in the Swagger UI: `POST /api/v1/models/sync` (admin), then `POST /api/v1/scoring/run`
(senior analyst). Alerts appear at `GET /api/v1/alerts`; rules can be tuned with
`PATCH /api/v1/rules/{id}` (admin).

### 8. Run the dashboard

In a second terminal (PowerShell or bash), with the API from step 5 still running:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 and sign in. The dev server forwards `/api` to the API on port 8000.
Create an analyst and a senior analyst with `create-user` (step 4) to try the full workflow: an
analyst works alerts and cases, and a senior analyst records case decisions and sees the audit log.

### 9. Run the tests and linters

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

Frontend (any shell, from `frontend`):

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

After changing API request or response models, regenerate the frontend types:
`python scripts/export_openapi.py` (from the repo root), then `npm run gen:api` in `frontend`.
CI fails if they are out of date.

## Repository layout

```
backend/            FastAPI app, SQLAlchemy models, Alembic migrations, tests
  app/api/v1/       Route handlers (health, auth, users, transactions, imports, scoring, alerts,
                    rules, models, cases, audit-events, metrics)
  app/core/         Settings, security, errors, middleware
  app/models/       Database tables
  app/schemas/      Request and response models (Pydantic)
  app/services/     Business logic (ingestion, scoring, rules, alerts, cases, model registry, audit)
  alembic/          Database migrations
  tests/            pytest suite (runs against real PostgreSQL)
frontend/           React + TypeScript dashboard (Vite); src/api/schema.d.ts is generated
ml/                 Offline training pipeline + shared feature code (see ml/README.md)
data/sample/        Small SYNTHETIC sample (not PaySim); data/raw/ is git-ignored
docs/               Plan, checklist, architecture, decisions, model report, limitations, demo,
                    phase reports, screenshots
scripts/            Sample-data generator, OpenAPI export, database init
.github/workflows/  CI
```

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
