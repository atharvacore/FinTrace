# Phase 3 Report: ML Pipeline

Date: 2026-10-11 · Status: **complete, with measured PaySim results** (update at the end of this file)

## Result

| | |
|---|---|
| Tests | **20 ML tests passed** (leakage, split, metrics, reproducibility, artifact). Backend's 83 unchanged |
| Lint | `ruff check` and `ruff format --check` clean for `ml/` |
| End-to-end runs | Inspection on the 5,000-row sample; training on a 100,000-row synthetic file in 7 s |
| Real results | **None yet.** No PaySim file is available in this environment, so no metric in this phase is a result |

## Complete

- `ml/` package (`fintrace-ml`): `data`, `inspect_data`, `features`, `split`, `evaluate`, `train`.
- **Data inspection report** (Markdown + JSON): rows, missing values, duplicates, imbalance overall and by type, amount quantiles, balance-inconsistency rates by class, zero-balance rates, `isFlaggedFraud` vs `isFraud`, fraud by split and by hour, leakage notes, dataset limitations.
- **Features**: 18 `strict` features (pre-transaction only) plus a 4-feature `with_post_balances` ablation. History counts from strictly earlier hours. Readable `risk_indicators` codes for Phase 4 alerts.
- **Chronological split** 70/15/15 by rows, cut between whole hours.
- **Models**: class-weighted logistic regression with scaling inside the pipeline (baseline) and histogram gradient boosting (improved). Thresholds and alert budgets chosen on validation; the model with the better validation average precision is kept; test scored once.
- **Metrics**: average precision with prevalence baseline, ROC AUC, precision, recall, F1, confusion matrix, alerts and false positives per 1,000 transactions, false positives per true positive, and an alert-budget table (top 0.1%, 0.5%, 1%, 2%).
- **Versioned artifact**: `model.joblib`, `metadata.json` (version, dataset and artifact sha256, split boundaries, methodology, every metric, library versions, seed), `report.md`. `--promote` copies it to `ml/artifacts/current` for the API.
- Synthetic runs are stamped "THESE ARE NOT RESULTS" in every report and `is_synthetic_demo: true` in metadata (tested).
- CI: new `ml` job (lint, tests, end-to-end smoke run).

## Incomplete

- **Measured model report on PaySim**: needs the dataset (see Blocked). The pipeline will produce it in one command; the report will then be copied to `docs/MODEL_REPORT.md`.
- Ablation comparison (`strict` vs `with_post_balances`) on PaySim: same dependency.

## Blocked

- **PaySim CSV.** Either attach the Kaggle zip in the project thread, or run on your own machine:
  `python -m fintrace_ml.inspect_data data/raw/paysim.csv --data-kind paysim --out ml/reports` then
  `python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --promote`.

## What the synthetic smoke run showed (not results)

On 100,000 synthetic rows the gradient-boosting model separated the classes perfectly. That is expected: the generator writes fraud with one fixed, scripted pattern. It shows the pipeline runs end to end, nothing more, which is exactly why synthetic numbers are never reported.

## Bugs found and fixed during this phase

- The `ml` package was installed before its `__init__.py` existed, so Python treated it as a namespace package and `from fintrace_ml import __version__` failed. Reinstalling fixed it; the README installs after checkout, so users will not hit this.

## Commands executed

```bash
pip install -e "ml[dev]"
python -m fintrace_ml.inspect_data data/sample/synthetic_transactions.csv --data-kind synthetic --out /tmp/rep
python scripts/generate_sample_data.py --rows 100000 --steps 240 --out /tmp/big.csv
python -m fintrace_ml.train /tmp/big.csv --data-kind synthetic --out /tmp/art     # 7 s
cd ml && pytest -q                    # 20 passed
ruff check . && ruff format --check .
```

## Files changed

New: `ml/pyproject.toml`, `ml/README.md`, `ml/fintrace_ml/{__init__,data,inspect_data,features,split,evaluate,train}.py`, `ml/tests/{__init__,conftest,test_features,test_split_and_metrics,test_pipeline}.py`, `docs/phases/PHASE-3.md`.
Modified: `.github/workflows/ci.yml` (ml job), `.gitignore` (`ml/reports/`), `README.md` (Getting PaySim, Train the model), `docs/CHECKLIST.md`, `docs/DECISIONS.md` (ADR-013 to ADR-016).

## How the code fits together (for interviews)

1. **Why chronological?** Fraud patterns drift. A random split lets the model learn from hours after the ones it is tested on, which flatters it. Splitting by time answers the real question: "trained on the past, how does it do next week?"
2. **Why average precision, not accuracy?** With ~0.13% fraud, predicting "never fraud" is 99.87% accurate. Average precision summarises the precision/recall trade-off and has an honest floor: a random model scores the prevalence.
3. **Why report alerts per 1,000?** An operations team has fixed review capacity. The alert-budget table answers "if we can review 1% of transactions, how much fraud do we catch and how many false alarms do analysts see?"
4. **Where leakage hides in PaySim.** `isFlaggedFraud` (a rule's output), account IDs (memorisation), post-transaction balances (simulator artefact), random splits (future information) and same-hour history counts. Each one has a guard and a test.
5. **Why two models?** The baseline sets a bar and is easy to explain; the boosted model must beat it on validation to be chosen. Both are reported on test so the comparison is visible.

---

## Update: PaySim run (same day)

Santa supplied the PaySim zip. It held one CSV (6,362,620 rows, expected header, sha256
`16910f90…4eea6b`), extracted to the git-ignored `data/raw/paysim.csv`.

- **Inspection:** [DATA_INSPECTION.md](../DATA_INSPECTION.md). 0.129% fraud, no missing values,
  16 zero-amount rows, fraud only in TRANSFER/CASH_OUT, and a big prevalence shift across the
  chronological split (train 0.082%, test 0.436%).
- **Results:** [MODEL_REPORT.md](../MODEL_REPORT.md). The strict gradient-boosting model reaches
  average precision 0.9999 on the test period. I checked why before reporting it: a transfer or
  cash-out of *exactly* the full balance is fraud in 8,018 of 8,018 cases, a simulator signature.
  A diagnostic run without origin-balance features gets 0.629, against a baseline of 0.362.
- **Code change:** added the `no_origin_balance` diagnostic feature set and its test (21 ML tests).
- **Commands:** `inspect_data` (1 min 16 s), strict training (5 min 43 s), two ablations (about
  18 min each, run in parallel).
