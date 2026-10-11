# Model Report: `hist-no_origin_balance-paysim-20261011075401`

- Data: `paysim.csv` (paysim), 6,362,620 rows, sha256 `16910f90577b0d98…`
- Features: `no_origin_balance` (14 features)
- Split: chronological by step; cuts between whole steps; train ≤ step 323 (4,463,587 rows), validation ≤ 378 (980,416), test ≤ 743 (918,617)
- Chosen model: **hist_gradient_boosting** (validation average_precision), operating threshold 0.476489
- Trained 2026-10-11T07:54:01.424270+00:00 with seed 42, scikit-learn 1.8.0

## Test-split results (thresholds fixed on validation)

Average precision of a random model equals the prevalence (0.004361).

| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | Alerts per 1,000 |
|---|---:|---:|---:|---:|---:|---|---:|
| logistic_regression | 0.362 | 0.9505 | 0.7912 | 0.2242 | 0.3493 | 898 / 237 / 3108 / 914374 | 1.236 |
| hist_gradient_boosting | 0.6289 | 0.9772 | 0.8857 | 0.3809 | 0.5327 | 1526 / 197 / 2480 / 914414 | 1.876 |

## Alert-budget trade-off on test (chosen model)

Each budget's threshold was set on validation so that the given share of transactions would alert; the table shows what that threshold does on the later test period.

| Budget | Threshold | Alerts per 1,000 | Precision | Recall | FP per TP |
|---|---:|---:|---:|---:|---:|
| top_0.1pct | 0.103124 | 3.503 | 0.6507 | 0.5227 | 0.54 |
| top_0.5pct | 0.020861 | 9.051 | 0.3563 | 0.7394 | 1.81 |
| top_1pct | 0.00398 | 15.988 | 0.2252 | 0.8255 | 3.44 |
| top_2pct | 0.001551 | 27.424 | 0.1352 | 0.8505 | 6.39 |

## Validation results (used for all choices)

| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | Alerts per 1,000 |
|---|---:|---:|---:|---:|---:|---|---:|
| logistic_regression | 0.2282 | 0.9438 | 0.6096 | 0.2021 | 0.3036 | 114 / 73 / 450 / 979779 | 0.191 |
| hist_gradient_boosting | 0.4293 | 0.9733 | 0.9543 | 0.3333 | 0.4941 | 188 / 9 / 376 / 979843 | 0.201 |

## Methodology

- History counts use strictly earlier steps only.
- All preprocessing is fitted on the training split only (inside the model pipeline).
- Thresholds (best-F1 and alert budgets) are chosen on validation, then fixed.
- The deployed model is the one with the higher validation average precision.
- Test metrics are computed once, after all choices were made.

## Responsible-use note

Scores are triage signals for human review. PaySim labels are simulated fraud, not confirmed money laundering. This model is not validated for real-world decisions.
