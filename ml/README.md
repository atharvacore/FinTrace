# FinTrace ML pipeline

Offline training and evaluation, separate from the API. The API only loads the artifact this
pipeline writes; it never trains.

| Module | Job |
|---|---|
| `data.py` | Load a PaySim-format CSV with explicit dtypes and schema checks |
| `inspect_data.py` | Data inspection report: imbalance, missing values, leakage, limitations |
| `features.py` | Feature engineering, **shared with the API** so online and offline features match |
| `split.py` | Chronological train / validation / test split by `step` |
| `evaluate.py` | PR-AUC, precision/recall/F1, confusion matrix, alert workload, thresholds |
| `train.py` | Runs everything and writes a versioned artifact |

## Commands

From the repository root, with the virtual environment active (same commands in PowerShell):

```bash
pip install -e "./ml[dev]"
python -m fintrace_ml.inspect_data data/raw/paysim.csv --data-kind paysim --out ml/reports
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --promote
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --feature-set with_post_balances   # ablation
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --feature-set no_origin_balance    # diagnostic
cd ml && pytest
```

`--promote` copies the artifact to `ml/artifacts/current`, which is where the API looks
(`FINTRACE_MODEL_DIR`).

A smoke run on the bundled synthetic sample works without PaySim, but its report is stamped
"THESE ARE NOT RESULTS":

```bash
python -m fintrace_ml.train data/sample/synthetic_transactions.csv --data-kind synthetic
```

## Leakage safeguards (all covered by tests)

- `isFlaggedFraud` and account IDs are never features.
- The default `strict` feature set uses only pre-transaction information; post-transaction
  balances appear only in the `with_post_balances` ablation.
- History counts use strictly earlier hours (`test_history_counts_only_see_strictly_earlier_steps`).
- Splits are chronological with no shared hour (`test_split_is_chronological_with_no_shared_steps`).
- Models are fitted on training rows only (`test_models_are_fitted_on_training_rows_only`) and the
  scaler's statistics equal the training rows' (`test_scaler_statistics_come_from_training_rows`).
- Thresholds are chosen on validation; test is scored once with them fixed.
- The same seed reproduces identical metrics (`test_same_seed_gives_identical_metrics`).

## Artifact layout

```
ml/artifacts/<version>/
  model.joblib     fitted scikit-learn model
  metadata.json    version, algorithm, features, threshold, split, all metrics, hashes, versions
  report.md        human-readable report
```
