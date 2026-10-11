# Model Report: `hist-strict-paysim-20261011073433`

- Data: `paysim.csv` (paysim), 6,362,620 rows, sha256 `16910f90577b0d98…`
- Features: `strict` (18 features)
- Split: chronological by step; cuts between whole steps; train ≤ step 323 (4,463,587 rows), validation ≤ 378 (980,416), test ≤ 743 (918,617)
- Chosen model: **hist_gradient_boosting** (validation average_precision), operating threshold 0.994511
- Trained 2026-10-11T07:34:33.116203+00:00 with seed 42, scikit-learn 1.8.0

## Test-split results (thresholds fixed on validation)

Average precision of a random model equals the prevalence (0.004361).

| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | Alerts per 1,000 |
|---|---:|---:|---:|---:|---:|---|---:|
| logistic_regression | 0.617 | 0.9963 | 0.7328 | 0.5107 | 0.6019 | 2046 / 746 / 1960 / 913865 | 3.039 |
| hist_gradient_boosting | 0.9999 | 1.0 | 0.9997 | 0.9885 | 0.9941 | 3960 / 1 / 46 / 914610 | 4.312 |

## Alert-budget trade-off on test (chosen model)

Each budget's threshold was set on validation so that the given share of transactions would alert; the table shows what that threshold does on the later test period.

| Budget | Threshold | Alerts per 1,000 | Precision | Recall | FP per TP |
|---|---:|---:|---:|---:|---:|
| top_0.1pct | 0.000214 | 4.71 | 0.9258 | 1.0 | 0.08 |
| top_0.5pct | 1.5e-05 | 8.484 | 0.514 | 1.0 | 0.95 |
| top_1pct | 6e-06 | 13.182 | 0.3308 | 1.0 | 2.02 |
| top_2pct | 3e-06 | 22.561 | 0.1933 | 1.0 | 4.17 |

## Validation results (used for all choices)

| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | Alerts per 1,000 |
|---|---:|---:|---:|---:|---:|---|---:|
| logistic_regression | 0.221 | 0.9965 | 0.2963 | 0.4876 | 0.3686 | 275 / 653 / 289 / 979199 | 0.947 |
| hist_gradient_boosting | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 564 / 0 / 0 / 979852 | 0.575 |

## Methodology

- History counts use strictly earlier steps only.
- All preprocessing is fitted on the training split only (inside the model pipeline).
- Thresholds (best-F1 and alert budgets) are chosen on validation, then fixed.
- The deployed model is the one with the higher validation average precision.
- Test metrics are computed once, after all choices were made.

## Responsible-use note

Scores are triage signals for human review. PaySim labels are simulated fraud, not confirmed money laundering. This model is not validated for real-world decisions.
