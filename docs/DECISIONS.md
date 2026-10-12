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

## ADR-013 Training is offline; the API shares only the feature code
`ml/` is its own package. The API will import `fintrace_ml.features` so online features are computed
by the same code as training features, but it never imports the training code. Artifacts are
plain files (`model.joblib` + `metadata.json`) copied into `FINTRACE_MODEL_DIR` by `--promote`.

## ADR-014 Evaluation protocol
Chronological split by hour (70/15/15 by rows, cut between whole hours). Both models are fitted on
train; each model's operating threshold (best F1) and alert-budget thresholds are chosen on
validation; the deployed model is the one with the higher validation average precision; test is
scored once with everything fixed. Average precision is reported next to the prevalence, because a
random model's average precision equals the prevalence. Workload is reported as alerts and false
positives per 1,000 transactions, which is what an operations team plans around.

## ADR-015 Strict features by default; post-transaction balances only as an ablation
PaySim's post-transaction balances make fraud almost trivially separable (destination balances are
often not updated for fraudulent transfers). A bank scoring a payment before it settles would not
have that information, so the default model does not use it. The `with_post_balances` run exists to
measure, and show, how much those columns inflate the numbers.

## ADR-016 Indicator codes are explanations, not model attributions
Each alert will carry readable indicator codes (for example `DRAINS_ORIGIN_BALANCE`,
`NEW_DESTINATION`) computed by transparent rules on the same inputs. They explain why a transaction
looks unusual; they do not claim to be what the gradient-boosting model weighted most. SHAP was not
added (see ADR-008).

## ADR-017 Keep the strict model, and publish the diagnostic next to it
On PaySim, a TRANSFER or CASH_OUT for exactly the full origin balance is always fraud (8,018 of
8,018 cases). The strict model learns this and scores almost perfectly. The signature uses only
pre-transaction information, so excluding it would be a judgement about the simulator, not about
leakage. The deployed model therefore keeps it, and the report shows the `no_origin_balance`
diagnostic (average precision 0.629) next to it so nobody mistakes 0.9999 for real-world skill.

## ADR-018 No model, no score
The spec's rule "never pretend to score" is enforced literally: every risk assessment has a
non-null `model_version_id` (database constraint, migration 0002). Without an active, hash-verified
model, scoring endpoints return `503 MODEL_NOT_AVAILABLE` with the training and registration
commands. Rules alone never produce a "risk score", because a rule hit count is not a probability.

## ADR-019 Model registry with copied, hash-checked artifacts
`POST /models/sync` copies the promoted artifact into `FINTRACE_MODEL_REGISTRY_DIR/<version>` and
records it in `model_versions`. Activation and every load re-check `model.joblib` against the sha256
in its metadata, so an edited or swapped file is refused (`409 MODEL_ARTIFACT_MODIFIED`). Older
versions stay available for rollback with `POST /models/{id}/activate`. `joblib` files are pickles,
so only artifacts produced by our own pipeline should ever be placed there.

## ADR-020 When an alert is raised
An alert is created when the model score reaches the operating threshold chosen on validation, or
when an enabled rule with severity `high` or `critical` fires. Medium rules add reason codes and
raise the level but do not alert alone. A transaction with an open alert does not get a second one
when re-scored. Risk level: at or above threshold = high (critical in the upper half of the
remaining range), at least half the threshold = medium, else low; a rule hit can raise the level to
its severity.

## ADR-021 `BALANCE_DRAIN` ships as a medium (non-alerting) rule
First end-to-end run on 200,000 PaySim rows: with `BALANCE_DRAIN` at high severity it raised 32,978
alerts (16.5% of all transactions), because 43% of legitimate PaySim transfers and cash-outs take the
whole balance. The model alone raised 137. The rule now ships as medium, so it explains alerts rather
than creating them. This is the classic rules-versus-model workload trade-off, measured.

Note that all four seeded rules are `medium`, so out of the box **no rule raises an alert on its
own**: alerts come from the model, and rules add reasons and raise the level. An admin can set a
rule to `high` (`PATCH /api/v1/rules/{id}`) to make it alerting; that change is audited.

## ADR-022 The API imports the shared feature code
The backend installs `ml/` as a package (`pip install -e ./ml -e ./backend[dev]`) and calls
`fintrace_ml.features.build_features`. History counts come from the database (strictly earlier
hours) instead of the CSV. `test_online_scores_match_offline_pipeline` checks that both paths give
the same score for all 5,000 sample transactions.

## ADR-023 Fixes from the Phase 1–4 review (2026-10-12)
A full code review before Phase 5 led to these changes (migration `0003`, 12 new tests):

- **Escalations are senior-only.** An analyst could move an escalated alert back to `in_review` and
  then close it. Analysts now cannot change the status of an escalated alert at all.
- **One open alert per transaction, also under concurrency.** Two scoring runs at once (CLI plus
  API) could both alert the same transaction. Scoring now takes a PostgreSQL advisory lock, and a
  partial unique index allows only one `open`/`in_review`/`escalated` alert per transaction.
  Reopening a closed alert while a newer one is open returns `409 ALERT_ALREADY_OPEN`.
- **Upload size is checked before the body is read.** FastAPI reads a multipart body before auth
  runs, so the 50 MB check in the route came too late. Middleware now rejects
  `POST /api/v1/imports` from its `Content-Length` (411 if missing, 413 if too big).
- **Model metadata is validated.** The version must be a plain name (it becomes a folder name) and
  the threshold must round to a value strictly between 0 and 1; otherwise `422`. Alert decisions use
  the full-precision score and threshold from the verified artifact, matching the offline
  evaluation exactly; the database keeps 5-decimal copies for display. Re-syncing a registered
  version restores its registry copy if that folder was lost.
- **Smaller fixes.** `step` must be ≥ 1 (PaySim starts at 1); naive `from`/`to` search times are
  read as UTC instead of failing with a 500; 500 responses carry the `X-Request-ID` header.
- **Known limitation, documented rather than changed:** `ORIGIN_VELOCITY` counts transactions in
  strictly earlier hours, the same as the model's history features. A burst within one PaySim hour
  is invisible to it, because PaySim gives no order inside an hour.
