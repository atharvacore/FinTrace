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

## ADR-009 Duplicate-safe imports with a dedup key and ON CONFLICT DO NOTHING
PaySim has no transaction ID. Each row gets `dedup_key = sha256(all business fields)`; API clients
must send an `external_id`, which becomes the key instead. Inserts use
`INSERT ... ON CONFLICT (dedup_key) DO NOTHING RETURNING`, so the database's unique index is the
final guard, even if two imports run at once. Trade-off: two genuinely identical PaySim rows
(same hour, type, accounts, amount and all four balances) would be stored once.
An API retry with the same `external_id` but a different payload is reported as `duplicate`, not
an error: the first write wins, as with an idempotency key.

## ADR-010 Simulated hours mapped to a fixed synthetic calendar
PaySim's `step` is an hour index (1 to 743). The app stores `step` and also
`occurred_at = 2026-01-01T00:00Z + (step - 1) hours` so the UI and date filters work. The dates are
synthetic and the UI must say so.

## ADR-011 `isFlaggedFraud` is ignored
It is the output of PaySim's own simple rule (transfers over 200,000), not ground truth. Storing or
using it as a model feature would leak a label proxy. `isFraud` is stored as
`label_is_fraud`, exposed only on the detail endpoint as `synthetic_label_is_fraud`, and used only
for evaluation.

## ADR-012 Rows are validated individually; bad rows never block good ones
A real import file often has a few bad lines. Each row is validated with the same Pydantic model the
API uses; good rows are inserted, bad rows are reported with their line number (first 100 stored,
all counted). Only an unusable file (wrong header, not UTF-8, not CSV) is rejected as a whole.
Balance arithmetic is not validated: PaySim itself contains inconsistent balances, which are a known
dataset quirk documented in Phase 3.
