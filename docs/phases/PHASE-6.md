# Phase 6 Report: Packaging, Demo and Polish

Date: 2026-10-12 · Branch `wip/phase-6` (built on Phase 5, pull request #2)

## Result

| | |
|---|---|
| Backend tests | **169 passed** on PostgreSQL 16 (167 after the priority fix + 2 for `demo-seed`) |
| ML tests | 21 passed (unchanged) |
| Frontend | `npm run typecheck`, `npm run lint`, `npm test` (**14 passed**) and `npm run build` all clean |
| Lint | `ruff check` and `ruff format --check` clean (backend, ml, scripts) |
| Docker | From a fresh clone: `docker compose up -d --build --wait` brings db, api and web up healthy; `demo-seed` run twice (second run adds nothing); readiness reports database, migration 0003 and model OK |
| Click-through | 15 scripted steps through nginx on port 8080 as the demo analyst and senior (assign, review, open case, note, decision, audit log, phone width, light theme): no console errors, no failed API calls |
| Priority fix | Re-scoring 200,000 PaySim rows (60 s) gives 34 critical and 103 high alerts instead of 135 critical and 2 high |

## Complete

### Packaging
- `backend/Dockerfile`: python:3.12-slim, non-root user, migrations on start, models in a named
  volume (ADR-027). `frontend/Dockerfile`: Node build, then nginx serving the app and proxying `/api`.
- `docker-compose.yml` runs `db`, `api` and `web` on 127.0.0.1 with health checks; ports are set in `.env`.
- `python -m app.cli demo-seed` (ADR-028): demo users, the synthetic sample, a model (the PaySim one
  if present, otherwise a clearly labelled synthetic model), scores and one example case. Idempotent.
- CI `docker` job: builds and starts the stack, seeds it twice, checks the page, the security
  headers, readiness, login and the overview numbers through the web proxy, then tears it down.

### Fixes found in this phase
- **Alert priority** (Santa's report that everything showed as critical): PaySim fraud scores are
  saturated (0.997–1.0), so the old score-band rule made 135 of 137 alerts critical. Critical now
  needs the model and at least two monitoring rules to agree (ADR-020, revised). Shipped on the
  Phase 4 branch and merged forward.
- **Security headers**: nginx dropped the content security policy on page routes because those
  locations set their own `Cache-Control` header. Fixed with a shared snippet (ADR-030).

### Dashboard redesign (ADR-029)
- An investigator's-ledger look: dark ink by default with a light paper theme switch on every page
  (including sign-in), serif headlines, monospaced figures, ruled tables, one heat scale for risk.
- Overview opens with the open-alert workload and a priority strip; the histogram shades the alert
  zone and labels the threshold; risk badges carry 1–4 pips; long reason lists collapse to "+N more".
- Sign-in page with the synthetic-data statement and an animated money-trail line (off when the
  browser asks for reduced motion). Fonts are bundled, so the content security policy stays `'self'`.

### Documentation
- docs/ARCHITECTURE.md (Mermaid diagram, request and data flow, model lifecycle, containers).
- docs/LIMITATIONS.md, docs/DEMO.md (a five-minute walk-through, run on the Docker stack),
  docs/RESUME.md (each bullet names the file that backs it).
- README: Docker quick start, screenshots, updated feature list; CHECKLIST: Phase 6 rows.
- `npm run screenshots` (frontend/scripts/screenshots.mjs) regenerates the 11 screenshots in
  docs/screenshots. It only reads; it changes nothing.

## Incomplete

- No user-management or CSV-upload screens: admins use the CLI or Swagger UI (`/docs`).
- The project was not run on a Windows machine. The PowerShell commands in the README are written
  out but untested on Windows.
- Everything in [docs/LIMITATIONS.md](../LIMITATIONS.md).

## Blocked

Nothing.

## Commands run

```bash
# backend (from backend/)
pytest                                   # 169 passed
ruff check . && ruff format --check .
# ml (from ml/)
pytest                                   # 21 passed
# frontend (from frontend/)
npm run typecheck && npm run lint && npm test && npm run build    # 14 passed
# Docker, from a fresh clone with a CI-style .env
docker compose up -d --build --wait
docker compose exec api python -m app.cli demo-seed               # twice
npm run screenshots                       # against the 200k-row PaySim dev database
```

## Files changed

- Backend: `app/cli.py` (demo-seed), `app/services/scoring.py` (priority), `tests/test_demo_seed.py`,
  `tests/test_models_and_scoring.py`, `backend/Dockerfile`, `.dockerignore`.
- Frontend: `Dockerfile`, `nginx.conf`, `security-headers.conf`, `.dockerignore`, `styles.css`,
  `main.tsx`, `lib/theme.ts`, components (`BrandMark`, `ThemeToggle`, `Layout`, `Badges`,
  `Histogram`), pages (`OverviewPage`, `LoginPage`, `AlertsPage`, `CaseDetailPage`),
  `scripts/screenshots.mjs`, a theme test, `package.json` (fonts, playwright-core).
- Root: `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, README, docs.
