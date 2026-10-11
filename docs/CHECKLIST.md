# FinTrace — Requirements Checklist

Legend: ✅ verified (test or command actually run) · 🟡 implemented, not yet verified · ⬜ not started · ⛔ blocked

Last updated: 2026-10-11 (end of Phase 1)

## Product
| Req | Status | Verified by |
|---|---|---|
| Import validated CSV files | ⬜ | AT-05, AT-06 |
| Accept transactions via REST API | ⬜ | AT-07 |
| Store transactions in PostgreSQL | 🟡 | Table + constraints in migration 0001 (`test_schema.py`); ingestion in Phase 2 |
| Configurable monitoring rules | ⬜ | AT-10 |
| Supervised ML model on labelled synthetic data | ⬜ | AT-14, AT-15 |
| Persist risk assessments (version, time, score, reasons) | ⬜ | AT-09 |
| Alerts: filter, assign, change status | ⬜ | AT-11 |
| Cases: link alerts, notes, decisions | ⬜ | AT-12 |
| Audit events for sensitive changes | 🟡 | User create / role change / password reset audited (`test_users_rbac.py`); more per phase |
| React dashboard (transactions, alerts, cases, metrics) | ⬜ | AT-16 |
| Reproducible training and evaluation pipeline | ⬜ | AT-14 |
| Docker Compose local run | 🟡 | `db` service verified: full test suite passed against it; api/web in Phase 6 |
| Tests, API docs, screenshots, README | ⬜ | AT-17 |

## Backend
| Req | Status | Verified by |
|---|---|---|
| Versioned REST API (/api/v1) | ✅ | All routes under /api/v1; OpenAPI at /docs (live smoke test) |
| Alembic migrations, FKs, constraints, indexes | ✅ | AT-01 `test_migrations_downgrade_and_upgrade_cleanly`; `alembic check` reports no drift |
| Pagination, validation, consistent errors | ✅ | `test_list_users_is_paginated`, `test_validation_errors_list_fields`, `test_unknown_route_uses_consistent_error_shape` |
| Duplicate-safe imports | ⬜ | AT-05 |
| Clear error when model artifact missing | 🟡 | Readiness reports `missing` (`test_readiness_...`); scoring 503 in Phase 4 |
| Auth + RBAC enforced server-side, password hashing | ✅ | AT-03, AT-04: `test_auth.py`, `test_users_rbac.py` |

## ML
| Req | Status | Verified by |
|---|---|---|
| PaySim instructions (no auto-download) | 🟡 | docs/PLAN.md §5 |
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
| GitHub Actions CI | 🟡 | `.github/workflows/ci.yml` (backend); first run after push |
| README, architecture diagram, model report, demo script | ⬜ | |
| Known limitations, truthful resume bullets | ⬜ | |
| No secrets committed (.env ignored, .env.example only) | ✅ | `.gitignore`; app refuses placeholder secret (`test_config.py`) |

## Phase log

| Phase | Date | Result |
|---|---|---|
| Planning | 2026-10-11 | docs/PLAN.md, this checklist |
| 1 Foundation | 2026-10-11 | 36 tests passed on PostgreSQL 16 (local and Docker Compose); ruff check + format clean |
