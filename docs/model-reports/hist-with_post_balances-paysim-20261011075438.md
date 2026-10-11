# Model Report: `hist-with_post_balances-paysim-20261011075438`

- Data: `paysim.csv` (paysim), 6,362,620 rows, sha256 `16910f90577b0d98…`
- Features: `with_post_balances` (22 features)
- Split: chronological by step; cuts between whole steps; train ≤ step 323 (4,463,587 rows), validation ≤ 378 (980,416), test ≤ 743 (918,617)
- Chosen model: **hist_gradient_boosting** (validation average_precision), operating threshold 0.997828
- Trained 2026-10-11T07:54:38.754893+00:00 with seed 42, scikit-learn 1.8.0

## Test-split results (thresholds fixed on validation)

Average precision of a random model equals the prevalence (0.004361).

| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | Alerts per 1,000 |
|---|---:|---:|---:|---:|---:|---|---:|
| logistic_regression | 0.7234 | 0.999 | 0.8034 | 0.7693 | 0.786 | 3082 / 754 / 924 / 913857 | 4.176 |
| hist_gradient_boosting | 0.9992 | 0.9999 | 1.0 | 0.992 | 0.996 | 3974 / 0 / 32 / 914611 | 4.326 |

## Alert-budget trade-off on test (chosen model)

Each budget's threshold was set on validation so that the given share of transactions would alert; the table shows what that threshold does on the later test period.

| Budget | Threshold | Alerts per 1,000 | Precision | Recall | FP per TP |
|---|---:|---:|---:|---:|---:|
| top_0.1pct | 9.9e-05 | 4.706 | 0.9257 | 0.999 | 0.08 |
| top_0.5pct | 8e-06 | 8.53 | 0.5107 | 0.999 | 0.96 |
| top_1pct | 4e-06 | 13.402 | 0.3252 | 0.9993 | 2.08 |
| top_2pct | 2e-06 | 22.986 | 0.1896 | 0.9995 | 4.27 |

## Validation results (used for all choices)

| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | Alerts per 1,000 |
|---|---:|---:|---:|---:|---:|---|---:|
| logistic_regression | 0.2856 | 0.9976 | 0.3702 | 0.7358 | 0.4926 | 415 / 706 / 149 / 979146 | 1.143 |
| hist_gradient_boosting | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 564 / 0 / 0 / 979852 | 0.575 |

## Methodology

- History counts use strictly earlier steps only.
- All preprocessing is fitted on the training split only (inside the model pipeline).
- Thresholds (best-F1 and alert budgets) are chosen on validation, then fixed.
- The deployed model is the one with the higher validation average precision.
- Test metrics are computed once, after all choices were made.

## Responsible-use note

Scores are triage signals for human review. PaySim labels are simulated fraud, not confirmed money laundering. This model is not validated for real-world decisions.
