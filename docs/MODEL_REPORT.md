# FinTrace Model Report (PaySim)

Measured on 2026-10-11 from real pipeline runs. Every number below comes from the artifacts in
[`docs/model-reports/`](model-reports/). Nothing is estimated or rounded up.

> **Read this first.** PaySim is simulated data. The near-perfect score of the deployed model
> comes mostly from a **simulator signature**, not from a fraud pattern you should expect in real
> payments (see "Why the scores are so high"). Labels are simulated fraud, not confirmed money
> laundering. Scores are triage signals for human review.

## Setup

| | |
|---|---|
| Data | PaySim, `PS_20174392719_1491204439457_log.csv`, 6,362,620 rows, sha256 `16910f90…4eea6b` |
| Fraud | 8,213 rows (0.129%, about 1 in 774), only in TRANSFER and CASH_OUT |
| Split | Chronological by `step` (hour), cut between whole hours: train ≤ 323 (4,463,587 rows), validation 324–378 (980,416), test 379–743 (918,617) |
| Models | Baseline: standardised features + class-weighted logistic regression. Improved: scikit-learn `HistGradientBoostingClassifier` |
| Choices | Each model's threshold (best F1) and alert budgets chosen on validation; model with the higher validation average precision is kept; test scored once |
| Environment | Python 3.12.3, scikit-learn 1.8.0, seed 42, 4 CPUs. Strict run took 5 min 43 s end to end |

Full inspection: [DATA_INSPECTION.md](DATA_INSPECTION.md).

## Results on the test period (steps 379–743)

Test prevalence is 0.436%, so a random model's average precision would be 0.0044.

| Feature set | Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN | Alerts per 1,000 |
|---|---|---:|---:|---:|---:|---:|---|---:|
| **strict** (deployed) | logistic regression | 0.617 | 0.996 | 0.733 | 0.511 | 0.602 | 2,046 / 746 / 1,960 | 3.04 |
| **strict** (deployed) | **gradient boosting** | **0.9999** | **1.000** | **0.9997** | **0.989** | **0.994** | 3,960 / 1 / 46 | 4.31 |
| no_origin_balance (diagnostic) | logistic regression | 0.362 | 0.951 | 0.791 | 0.224 | 0.349 | 898 / 237 / 3,108 | 1.24 |
| no_origin_balance (diagnostic) | gradient boosting | 0.629 | 0.977 | 0.886 | 0.381 | 0.533 | 1,526 / 197 / 2,480 | 1.88 |
| with_post_balances (ablation) | logistic regression | 0.723 | 0.999 | 0.803 | 0.769 | 0.786 | 3,082 / 754 / 924 | 4.18 |
| with_post_balances (ablation) | gradient boosting | 0.999 | 1.000 | 1.000 | 0.992 | 0.996 | 3,974 / 0 / 32 | 4.33 |

Gradient boosting beat the baseline on validation in all three runs, so it was the model kept each
time.

## Why the scores are so high

A check on the full dataset found that in PaySim, a TRANSFER or CASH_OUT for **exactly** the full
pre-transaction balance happens 8,018 times, and **every one** of them is fraud. No legitimate
transaction does it. 97.6% of all frauds have this pattern. The `strict` features include the
amount and the pre-transaction balance, which a bank would know when a payment is requested, so
this is not leakage of future information. The gradient-boosting model learns the exact-equality
signature from the amount-to-balance ratio. The simulator writes it into every fraud it generates;
real fraudsters do not always empty an account to the cent.

The `no_origin_balance` run removes every origin-balance feature to measure how much the model
leans on that signature. Average precision drops from 0.9999 to 0.629 and recall at the
operating threshold from 0.989 to 0.381. That run is the better guide to how hard the problem is
without the simulator's tell. It is still PaySim, though, so it is not a real-world estimate either.

The `with_post_balances` ablation adds post-transaction balances. It barely changes gradient
boosting, which was already near the ceiling, but lifts the baseline from 0.617 to 0.723 average
precision. Those columns stay out of the deployed model on principle (ADR-015).

## Alert workload (deployed strict model, test period)

Thresholds were set on validation so that the given share of validation transactions would alert.

| Budget (set on validation) | Alerts per 1,000 on test | Precision | Recall | False positives per true positive |
|---|---:|---:|---:|---:|
| Operating threshold (best F1) | 4.31 | 0.9997 | 0.989 | 0.00 |
| Top 0.1% | 4.71 | 0.926 | 1.000 | 0.08 |
| Top 0.5% | 8.48 | 0.514 | 1.000 | 0.95 |
| Top 1% | 13.18 | 0.331 | 1.000 | 2.02 |
| Top 2% | 22.56 | 0.193 | 1.000 | 4.17 |

Without the origin-balance signature (`no_origin_balance`), a top-1% budget catches 82.6% of
fraud at 3.4 false positives per true positive. That is the more instructive trade-off for an
interview.

## Caveats

- **Prevalence shift.** Fraud is 0.082% of training rows, 0.057% of validation rows and 0.436% of
  test rows. PaySim's transaction volume falls sharply after about step 400 while fraud continues
  at a steady rate. Precision on test is not directly comparable with precision on validation.
- **Validation saturation.** The strict and post-balance gradient-boosting models were perfect on
  validation (564 of 564 frauds, 0 false positives). So the "best-F1 threshold" was picked from a
  curve with no trade-off left, and budget thresholds on validation sit at very small scores.
- **One simulator, one fraud script.** Fraud appears only as account takeover, then transfer, then
  cash-out. Other fraud types and money-laundering typologies are absent.
- **Thin history.** 99.85% of origin accounts appear once, so per-customer behaviour features
  carry little signal.
- **16 rows with amount 0** are kept for training but would be rejected by the importer (amount
  must be positive).
- **Not validated** for any real-world decision. Not an AML model.

## Reproduce

```bash
python -m fintrace_ml.inspect_data data/raw/paysim.csv --data-kind paysim --out ml/reports
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --promote
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --feature-set no_origin_balance
python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --feature-set with_post_balances
```

Same data and seed give the same metrics (`test_same_seed_gives_identical_metrics`); only the
timestamped version names and fit times differ.
