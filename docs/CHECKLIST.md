# FinTrace — Requirements Checklist

Legend: ✅ verified (test or command actually run) · 🟡 implemented, not yet verified · ⬜ not started · ⛔ blocked

Last updated: 2026-10-12 (end of Phase 4)

## Product
| Req | Status | Verified by |
|---|---|---|
| Import validated CSV files | ✅ | AT-05, AT-06: `test_imports.py` (row-level errors, header checks, size limit, UTF-8) |
| Accept transactions via REST API | ✅ | `test_transactions.py` (idempotent by external_id, validation, 1000-row cap) |
| Store transactions in PostgreSQL | ✅ | `test_valid_csv_is_imported`, `test_schema.py` constraints |
| Configurable monitoring rules | ✅ | AT-10 `test_tuning_a_rule_changes_alert_outcomes`, `test_rule_types`, `test_invalid_parameters_are_rejected` |
| Supervised ML model on labelled synthetic data | ✅ | Trained on full PaySim; docs/MODEL_REPORT.md |
| Persist risk assessments (version, time, score, reasons) | ✅ | AT-09 `test_assessment_is_persisted_with_version_time_score_and_reasons`; parity `test_online_scores_match_offline_pipeline` |
| Alerts: filter, assign, change status | ✅ | AT-11 `test_alerts.py` (filters, sorting, permissions, transitions, audit) |
| Cases: link alerts, notes, decisions | ⬜ | AT-12 |
| Audit events for sensitive changes | 🟡 | Users, imports, ingestion, rule edits, model registration/activation, scoring, alert changes audited (tests in each file); cases in Phase 5 |
| React dashboard (transactions, alerts, cases, metrics) | ⬜ | AT-16 |
| Reproducible training and evaluation pipeline | ✅ | AT-14 `test_same_seed_gives_identical_metrics`; CI smoke run on synthetic sample |
| Docker Compose local run | 🟡 | `db` service verified: full test suite passed against it; api/web in Phase 6 |
| Tests, API docs, screenshots, README | ⬜ | AT-17 |

## Backend
| Req | Status | Verified by |
|---|---|---|
| Versioned REST API (/api/v1) | ✅ | All routes under /api/v1; OpenAPI at /docs (live smoke test) |
| Alembic migrations, FKs, constraints, indexes | ✅ | AT-01 `test_migrations_downgrade_and_upgrade_cleanly`; `alembic check` reports no drift |
| Pagination, validation, consistent errors | ✅ | AT-07 `test_search_filters_and_sorting`, `test_search_pagination_totals`, `test_validation_errors_list_fields` |
| Duplicate-safe imports | ✅ | AT-05 `test_reimporting_same_file_inserts_nothing`, `test_same_external_id_twice_in_one_request` |
| Clear error when model artifact missing | ✅ | AT-08 `test_scoring_without_a_model_is_503_with_instructions`, `test_tampered_artifact_is_refused` |
| Auth + RBAC enforced server-side, password hashing | ✅ | AT-03, AT-04: `test_auth.py`, `test_users_rbac.py` |

## ML
| Req | Status | Verified by |
|---|---|---|
| PaySim instructions (no auto-download) | ✅ | README 'Getting PaySim'; nothing downloads data |
| Data inspection: imbalance, missing values, limitations, leakage | ✅ | docs/DATA_INSPECTION.md (PaySim run) |
| Baseline + improved model | ✅ | Logistic regression vs gradient boosting on PaySim, three feature sets (docs/MODEL_REPORT.md) |
| Chronological evaluation, train-only preprocessing | ✅ | `test_split_is_chronological...`, `test_models_are_fitted_on_training_rows_only`, `test_scaler_statistics_come_from_training_rows`, `test_history_counts_only_see_strictly_earlier_steps` |
| P/R/F1, PR-AUC, confusion matrix, FP workload, thresholds | ✅ | AT-15: docs/MODEL_REPORT.md and docs/model-reports/ |
| Model version and methodology recorded | ✅ | `metadata.json` (version, hashes, split, methodology, library versions) |

## Frontend
| Req | Status | Verified by |
|---|---|---|
| Overview metrics + risk distribution | ⬜ | |
| Searchable, filterable transactions | ⬜ | |
| Alert queue (priority, status, score, reasons) | ⬜ | |
| Transaction detail + investigation history | ⬜ | |
| Case creation, assignment, notes, status | ⬜ | |
| Model evaluation + synthetic-data labels | ⬜ | |
| Loading, empty, validation, error states | ⬜ | AT-16 |

## Delivery
| Req | Status | Verified by |
|---|---|---|
| Plan: architecture, schema, API, milestones, deps, risks | ✅ | docs/PLAN.md |
| GitHub Actions CI | ✅ | `.github/workflows/ci.yml` backend job green on run 38119907866 |
| README, architecture diagram, model report, demo script | ⬜ | |
| Known limitations, truthful resume bullets | ⬜ | |
| No secrets committed (.env ignored, .env.example only) | ✅ | `.gitignore`; app refuses placeholder secret (`test_config.py`) |

## Phase log

| Phase | Date | Result |
|---|---|---|
| Planning | 2026-10-11 | docs/PLAN.md, this checklist |
| 1 Foundation | 2026-10-11 | 36 tests passed on PostgreSQL 16 (local and Docker Compose); ruff check + format clean |
| 2 Ingestion | 2026-10-11 | 83 tests passed; ruff clean (backend + scripts); 100k-row import in 20 s |
| 3 ML pipeline | 2026-10-11 | 21 ML tests passed; ruff clean; PaySim inspected and trained (strict + 2 ablations) |
| 4 Scoring + alerts | 2026-10-12 | 131 backend tests passed; ruff clean; 200,000 PaySim rows imported and scored with the real model |
