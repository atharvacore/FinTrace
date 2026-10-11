# Data Inspection Report

- Source: `paysim.csv` (sha256 `16910f90577b0d98…`)
- Rows: 6,362,620 · steps 1–743
- Fraud rows: 8,213 (0.129%), about 1 in 774
- Missing values: 0 in total
- Exact duplicate rows: 0
- Rows with amount ≤ 0: 16

## Class balance by type

| Type | Rows | Frauds | Fraud rate |
|---|---:|---:|---:|
| CASH_IN | 1,399,284 | 0 | 0.000% |
| CASH_OUT | 2,237,500 | 4,116 | 0.184% |
| DEBIT | 41,432 | 0 | 0.000% |
| PAYMENT | 2,151,495 | 0 | 0.000% |
| TRANSFER | 532,909 | 4,097 | 0.769% |

## Chronological split (by step)

Boundaries: train ≤ 323, valid ≤ 378, test ≤ 743.

| Split | Rows | Frauds | Fraud rate |
|---|---:|---:|---:|
| train | 4,463,587 | 3,643 | 0.082% |
| valid | 980,416 | 564 | 0.057% |
| test | 918,617 | 4,006 | 0.436% |

If fraud rates differ a lot between splits, metrics on the test split are not directly comparable with validation metrics; precision in particular rises with prevalence.

## Balance consistency (TRANSFER and CASH_OUT)

Share of rows where `old − amount ≠ new` (origin) or `old + amount ≠ new` (destination):

```json
{
  "legit": {
    "origin": 0.9051,
    "destination": 0.2258
  },
  "fraud": {
    "origin": 0.0055,
    "destination": 0.565
  }
}
```

## Other checks

```json
{
  "amount_quantiles": {
    "legit": {
      "0.5": 74684.72,
      "0.9": 364373.44,
      "0.99": 1586064.17
    },
    "fraud": {
      "0.5": 441423.44,
      "0.9": 4521723.51,
      "0.99": 10000000.0
    }
  },
  "origin_balance_zero_before_rate": {
    "legit": 0.3309,
    "fraud": 0.005
  },
  "fraud_amount_equals_origin_balance_rate": 0.9782,
  "origin_accounts_seen_once_rate": 0.9985,
  "merchant_destination_rate": 0.3381,
  "isFlaggedFraud": {
    "flagged": 16,
    "flagged_and_fraud": 16,
    "share_of_frauds_flagged": 0.0019
  }
}
```

## Leakage risks and how the pipeline handles them

- `isFlaggedFraud` is the output of PaySim's own rule (TRANSFER > 200,000). It is a label proxy and is excluded from features.
- `nameOrig` / `nameDest` are identifiers. Used only to count earlier activity, never as features, so the model cannot memorise accounts.
- `newbalanceOrig` / `newbalanceDest` describe the state after the transaction. In PaySim, fraudulent transfers often leave destination balances unchanged, so 'balance error' features separate the classes almost perfectly. That is a simulator artefact, not a fraud signal a bank could rely on, so they are excluded from the default `strict` feature set and shown only as an ablation.
- Random row splits would let the model train on hours that come after the test period. Evaluation uses a chronological split by `step`.
- History counts (earlier transactions per account) use strictly earlier steps only.

## Dataset limitations

- PaySim is a simulation calibrated on one month of logs from a mobile-money service in one African country. Patterns may not transfer to other payment systems.
- Fraud appears only in TRANSFER and CASH_OUT in PaySim, and follows one scripted pattern (take over account, transfer out, cash out).
- Labels mark simulated fraud. They are not confirmed money-laundering cases and must not be described as AML ground truth.
- Most origin accounts appear once, so per-customer behavioural history is very thin.
