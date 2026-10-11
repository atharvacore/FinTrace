# FinTrace — Requirements Checklist

Legend: ✅ verified (test or command actually run) · 🟡 implemented, not yet verified · ⬜ not started · ⛔ blocked

Last updated: 2026-10-11 (end of Phase 2)

## Product
| Req | Status | Verified by |
|---|---|---|
| Import validated CSV files | ✅ | AT-05, AT-06: `test_imports.py` (row-level errors, header checks, size limit, UTF-8) |
| Accept transactions via REST API | ✅ | `test_transactions.py` (idempotent by external_id, validation, 1000-row cap) |
| Store transactions in PostgreSQL | ✅ | `test_valid_csv_is_imported`, `test_schema.py` constraints |
| Configurable monitoring rules | ⬜ | AT-10 |
| Supervised ML model on labelled synthetic data | ⬜ | AT-14, AT-15 |
| Persist risk assessments (version, time, score, reasons) | ⬜ | AT-09 |
| Alerts: filter, assign, change status | ⬜ | AT-11 |
| Cases: link alerts, notes, decisions | ⬜ | AT-12 |
| Audit events for sensitive changes | 🟡 | Users, imports, API ingestion audited (`test_users_rbac.py`, `test_imports.py`, `test_transactions.py`); alerts/cases/rules in Phases 4–5 |
| React dashboard (transactions, alerts, cases, metrics) | ⬜ | AT-16 |
| Reproducible training and evaluation pipeline | ⬜ | AT-14 |
| Docker Compose local run | 🟡 | `db` service verified: full test suite passed against it; api/web in Phase 6 |
| Tests, API docs, screenshots, README | ⬜ | AT-17 |

## Backend
| Req | Status | Verified by |
|---|---|---|
| Versioned REST API (/api/v1) | ✅ | All routes under /api/v1; OpenAPI at /docs (live smoke test) |
| Alembic migrations, FKs, constraints, indexes | ✅ | AT-01 `test_migrations_downgrade_and_upgrade_cleanly`; `alembic check` reports no drift |
| Pagination, validation, consistent errors | ✅ | AT-07 `test_search_filters_and_sorting`, `test_search_pagination_totals`, `test_validation_errors_list_fields` |
| Duplicate-safe imports | ✅ | AT-05 `test_reimporting_same_file_inserts_nothing`, `test_same_external_id_twice_in_one_request` |
| Clear error when model artifact missing | 🟡 | Readiness reports `missing` (`test_readiness_...`); scoring 503 in Phase 4 |
| Auth + RBAC enforced server-side, password hashing | ✅ | AT-03, AT-04: `test_auth.py`, `test_users_rbac.py` |

## ML
| Req | Status | Verified by |
|---|---|---|
| PaySim instructions (no auto-download) | 🟡 | docs/PLAN.md §5; synthetic stand-in in data/sample (reproducibility test) |
| Data inspection: imbalance, missing values, limitations, leakage | ⬜ | |
| Baseline + improved model | ⬜ | |
| Chronological evaluation, train-only preprocessing | ⬜ | AT-14 |
| P/R/F1, PR-AUC, confusion matrix, FP workload, thresholds | ⬜ | AT-15 |
| Model version and methodology recorded | ⬜ | |

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
