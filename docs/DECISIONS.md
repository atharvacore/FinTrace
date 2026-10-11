# Architecture Decisions

Short records of decisions that a reviewer or interviewer might ask "why?" about.

## ADR-001 PostgreSQL for tests, not SQLite
The schema relies on PostgreSQL features (JSONB, arrays, partial unique indexes, CHECK constraints).
Testing on SQLite would hide real failures. Tests run the real Alembic migrations on a disposable
PostgreSQL database, locally and in CI.

## ADR-002 Enums stored as VARCHAR + CHECK constraint
Native PostgreSQL enums are awkward to change in migrations. VARCHAR with a CHECK constraint gives
the same protection and is easy to evolve.

## ADR-003 Money as NUMERIC(18,2)
Floating-point types cannot represent many decimal amounts exactly. The ML pipeline converts to
floats for modelling only.

## ADR-004 No cascading deletes
Every foreign key is `ON DELETE RESTRICT`. Financial records, alerts and decisions should never
disappear because a related row was deleted.

## ADR-005 JWT access tokens, roles checked on the server
A short-lived bearer token is enough for a single-service prototype. Every protected route
declares its minimum role through a FastAPI dependency (`require_role`), so the UI hiding a button
is never the only protection. Trade-off: no refresh tokens or revocation list; deactivating a user
blocks them immediately because each request reloads the user.

## ADR-006 Argon2id password hashing via pwdlib
Argon2id is the current OWASP recommendation. Login runs a dummy hash check for unknown emails so
response time does not reveal which accounts exist, and all login failures return the same message.

## ADR-007 Model artifact is optional for readiness
Without a model the API still runs and rules can still score; readiness reports the model as
`missing` with the command to fix it. Scoring endpoints that need the model will return
`503 MODEL_NOT_AVAILABLE` rather than inventing a score.

## ADR-008 scikit-learn only (no XGBoost or SHAP for now)
`HistGradientBoostingClassifier` covers gradient boosting without a native install, which keeps
setup reliable on Windows. Revisit only if Phase 3 measurements show a real gap.
