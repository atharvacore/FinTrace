# Resume Bullets

Each bullet is backed by something in this repository; the source is listed under it. Pick three or
four. Do not round the numbers up, and keep the word "synthetic".

**FinTrace — financial crime detection and investigation prototype** (Python, FastAPI, PostgreSQL,
scikit-learn, React, TypeScript, Docker)

- Built a full-stack transaction-monitoring prototype: CSV/JSON ingestion with row-level
  validation, ML and rule-based scoring, an alert queue, investigation cases and an audit trail,
  served by a FastAPI backend on PostgreSQL and a React + TypeScript dashboard.
  - *Source:* README, docs/ARCHITECTURE.md
- Trained a fraud classifier on the 6.36-million-row synthetic PaySim dataset with a chronological
  train/validation/test split. Gradient boosting reached 0.9999 test average precision against a
  0.617 logistic-regression baseline. I traced the near-perfect score to a simulator artefact
  (full-balance transfers are always fraud) and reported a 0.629 diagnostic without it.
  - *Source:* docs/MODEL_REPORT.md
- Prevented training/serving skew by sharing one feature module between the training pipeline and
  the API, with a test that checks online scores match offline scores on 5,000 transactions.
  Model artifacts are versioned and sha256-checked before use.
  - *Source:* `test_online_scores_match_offline_pipeline`, services/model_registry.py
- Designed alert priority around agreement between evidence sources (the model and at least two
  monitoring rules for "critical") after finding that saturated model scores made 135 of 137 alerts
  critical. The change gave 34 critical and 103 high on 200,000 PaySim transactions.
  - *Source:* docs/DECISIONS.md ADR-020
- Enforced role-based access (analyst, senior analyst, admin) on the server, with Argon2 password
  hashing, JWT auth and audit events written in the same database transaction as each change.
  - *Source:* test_users_rbac.py, test_cases.py, test_audit_and_metrics.py
- Wrote 209 automated tests (169 backend against real PostgreSQL, 21 ML, 19 frontend), run in GitHub Actions
  with lint, type checks, OpenAPI drift checks and a Docker Compose job that builds the stack, seeds
  demo data and checks the app through the web proxy.
  - *Source:* .github/workflows/ci.yml

## Words to avoid

"Production-grade", "detects money laundering", "bank-ready", "99.99% accurate". None of these is
true. Labels are simulated fraud on synthetic data, and the score is a triage signal for a person.
