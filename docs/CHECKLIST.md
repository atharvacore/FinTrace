# FinTrace — Requirements Checklist

Legend: ✅ verified (test or command actually run) · 🟡 implemented, not yet verified · ⬜ not started · ⛔ blocked

Last updated: 2026-10-11 (planning)

## Product
| Req | Status | Verified by |
|---|---|---|
| Import validated CSV files | ⬜ | AT-05, AT-06 |
| Accept transactions via REST API | ⬜ | AT-07 |
| Store transactions in PostgreSQL | ⬜ | AT-01 |
| Configurable monitoring rules | ⬜ | AT-10 |
| Supervised ML model on labelled synthetic data | ⬜ | AT-14, AT-15 |
| Persist risk assessments (version, time, score, reasons) | ⬜ | AT-09 |
| Alerts: filter, assign, change status | ⬜ | AT-11 |
| Cases: link alerts, notes, decisions | ⬜ | AT-12 |
| Audit events for sensitive changes | ⬜ | AT-13 |
| React dashboard (transactions, alerts, cases, metrics) | ⬜ | AT-16 |
| Reproducible training and evaluation pipeline | ⬜ | AT-14 |
| Docker Compose local run | ⬜ | AT-17 |
| Tests, API docs, screenshots, README | ⬜ | AT-17 |

## Backend
| Req | Status | Verified by |
|---|---|---|
| Versioned REST API (/api/v1) | ⬜ | |
| Alembic migrations, FKs, constraints, indexes | ⬜ | AT-01 |
| Pagination, validation, consistent errors | ⬜ | |
| Duplicate-safe imports | ⬜ | AT-05 |
| Clear error when model artifact missing | ⬜ | AT-08 |
| Auth + RBAC enforced server-side, password hashing | ⬜ | AT-03, AT-04 |

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
| GitHub Actions CI | ⬜ | |
| README, architecture diagram, model report, demo script | ⬜ | |
| Known limitations, truthful resume bullets | ⬜ | |
| No secrets committed (.env ignored, .env.example only) | ⬜ | |
