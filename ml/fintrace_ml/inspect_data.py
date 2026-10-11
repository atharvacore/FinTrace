"""Data inspection: run this before choosing features.

    python -m fintrace_ml.inspect_data data/raw/paysim.csv --data-kind paysim --out ml/reports

Writes `data_inspection.json` and `data_inspection.md` with class imbalance, missing values,
duplicates, balance inconsistencies, label-proxy checks and how fraud is spread over time.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from fintrace_ml.data import LABEL, file_sha256, load_paysim
from fintrace_ml.split import chronological_split

LEAKAGE_NOTES = [
    "`isFlaggedFraud` is the output of PaySim's own rule (TRANSFER > 200,000). It is a label "
    "proxy and is excluded from features.",
    "`nameOrig` / `nameDest` are identifiers. Used only to count earlier activity, never as "
    "features, so the model cannot memorise accounts.",
    "`newbalanceOrig` / `newbalanceDest` describe the state after the transaction. In PaySim, "
    "fraudulent transfers often leave destination balances unchanged, so 'balance error' features "
    "separate the classes almost perfectly. That is a simulator artefact, not a fraud signal a "
    "bank could rely on, so they are excluded from the default `strict` feature set and shown "
    "only as an ablation.",
    "Random row splits would let the model train on hours that come after the test period. "
    "Evaluation uses a chronological split by `step`.",
    "History counts (earlier transactions per account) use strictly earlier steps only.",
]
LIMITATION_NOTES = [
    "PaySim is a simulation calibrated on one month of logs from a mobile-money service in one "
    "African country. Patterns may not transfer to other payment systems.",
    "Fraud appears only in TRANSFER and CASH_OUT in PaySim, and follows one scripted pattern "
    "(take over account, transfer out, cash out).",
    "Labels mark simulated fraud. They are not confirmed money-laundering cases and must not be "
    "described as AML ground truth.",
    "Most origin accounts appear once, so per-customer behavioural history is very thin.",
]


def _pct(x: float) -> str:
    return f"{100 * x:.3f}%"


def inspect(df: pd.DataFrame) -> dict:
    n = len(df)
    fraud = df[LABEL] == 1
    by_type = (
        df.groupby("type", observed=True)[LABEL]
        .agg(rows="size", frauds="sum")
        .assign(fraud_rate=lambda t: (t["frauds"] / t["rows"]).round(6))
    )

    orig_err = (df["oldbalanceOrg"] - df["amount"] - df["newbalanceOrig"]).abs() > 0.01
    dest_err = (df["oldbalanceDest"] + df["amount"] - df["newbalanceDest"]).abs() > 0.01
    money_types = df["type"].isin(["TRANSFER", "CASH_OUT"])

    report: dict = {
        "rows": n,
        "columns": list(df.columns),
        "missing_values": {c: int(v) for c, v in df.isna().sum().items()},
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "step_range": [int(df["step"].min()), int(df["step"].max())],
        "distinct_steps": int(df["step"].nunique()),
        "frauds": int(fraud.sum()),
        "fraud_rate": round(float(fraud.mean()), 6),
        "imbalance_ratio": round(float((~fraud).sum() / max(fraud.sum(), 1)), 1),
        "by_type": by_type.reset_index().to_dict(orient="records"),
        "zero_amount_rows": int((df["amount"] <= 0).sum()),
        "amount_quantiles": {
            label: {
                q: round(float(v), 2)
                for q, v in df.loc[mask, "amount"].quantile([0.5, 0.9, 0.99]).items()
            }
            for label, mask in (("legit", ~fraud), ("fraud", fraud))
            if mask.any()
        },
        "balance_inconsistency_rate_transfer_cashout": {
            label: {
                "origin": round(float(orig_err[money_types & mask].mean()), 4),
                "destination": round(float(dest_err[money_types & mask].mean()), 4),
            }
            for label, mask in (("legit", ~fraud), ("fraud", fraud))
            if (money_types & mask).any()
        },
        "origin_balance_zero_before_rate": {
            "legit": round(float((df.loc[~fraud, "oldbalanceOrg"] == 0).mean()), 4),
            "fraud": round(float((df.loc[fraud, "oldbalanceOrg"] == 0).mean()), 4)
            if fraud.any()
            else None,
        },
        "fraud_amount_equals_origin_balance_rate": round(
            float((df.loc[fraud, "amount"] == df.loc[fraud, "oldbalanceOrg"]).mean()), 4
        )
        if fraud.any()
        else None,
        "origin_accounts_seen_once_rate": round(
            float((df["nameOrig"].value_counts() == 1).mean()), 4
        ),
        "merchant_destination_rate": round(float(df["nameDest"].str.startswith("M").mean()), 4),
    }
    if "isFlaggedFraud" in df:
        flagged = df["isFlaggedFraud"] == 1
        report["isFlaggedFraud"] = {
            "flagged": int(flagged.sum()),
            "flagged_and_fraud": int((flagged & fraud).sum()),
            "share_of_frauds_flagged": round(
                float((flagged & fraud).sum() / max(fraud.sum(), 1)), 4
            ),
        }

    train, valid, test, bounds = chronological_split(df)
    report["chronological_split"] = {
        "boundaries": bounds.as_dict(),
        **{
            name: {
                "rows": int(mask.sum()),
                "frauds": int(df.loc[mask, LABEL].sum()),
                "fraud_rate": round(float(df.loc[mask, LABEL].mean()), 6),
            }
            for name, mask in (("train", train), ("valid", valid), ("test", test))
        },
    }
    hours = (df["step"] - 1) % 24
    report["fraud_rate_by_hour_of_day"] = {
        int(h): round(float(r), 6) for h, r in df.groupby(hours)[LABEL].mean().items()
    }
    report["leakage_notes"] = LEAKAGE_NOTES
    report["limitations"] = LIMITATION_NOTES
    return report


def to_markdown(report: dict, source: str, data_kind: str) -> str:
    lines = ["# Data Inspection Report", ""]
    if data_kind != "paysim":
        lines += [
            "> **SYNTHETIC SAMPLE, NOT PAYSIM.** Generated by `scripts/generate_sample_data.py` "
            "for smoke tests. Nothing here describes real or PaySim data.",
            "",
        ]
    lines += [
        f"- Source: `{source}` (sha256 `{report['sha256'][:16]}…`)",
        f"- Rows: {report['rows']:,} · steps {report['step_range'][0]}–{report['step_range'][1]}",
        f"- Fraud rows: {report['frauds']:,} ({_pct(report['fraud_rate'])}), "
        f"about 1 in {report['imbalance_ratio']:,.0f}",
        f"- Missing values: {sum(report['missing_values'].values())} in total",
        f"- Exact duplicate rows: {report['exact_duplicate_rows']}",
        f"- Rows with amount ≤ 0: {report['zero_amount_rows']}",
        "",
        "## Class balance by type",
        "",
        "| Type | Rows | Frauds | Fraud rate |",
        "|---|---:|---:|---:|",
    ]
    for r in report["by_type"]:
        lines.append(f"| {r['type']} | {r['rows']:,} | {r['frauds']:,} | {_pct(r['fraud_rate'])} |")
    split = report["chronological_split"]
    lines += [
        "",
        "## Chronological split (by step)",
        "",
        f"Boundaries: train ≤ {split['boundaries']['train_last_step']}, "
        f"valid ≤ {split['boundaries']['valid_last_step']}, "
        f"test ≤ {split['boundaries']['test_last_step']}.",
        "",
        "| Split | Rows | Frauds | Fraud rate |",
        "|---|---:|---:|---:|",
    ]
    for name in ("train", "valid", "test"):
        s = split[name]
        lines.append(f"| {name} | {s['rows']:,} | {s['frauds']:,} | {_pct(s['fraud_rate'])} |")
    lines += [
        "",
        "If fraud rates differ a lot between splits, metrics on the test split are not directly "
        "comparable with validation metrics; precision in particular rises with prevalence.",
        "",
        "## Balance consistency (TRANSFER and CASH_OUT)",
        "",
        "Share of rows where `old − amount ≠ new` (origin) or `old + amount ≠ new` (destination):",
        "",
        "```json",
        json.dumps(report["balance_inconsistency_rate_transfer_cashout"], indent=2),
        "```",
        "",
        "## Other checks",
        "",
        "```json",
        json.dumps(
            {
                k: report[k]
                for k in (
                    "amount_quantiles",
                    "origin_balance_zero_before_rate",
                    "fraud_amount_equals_origin_balance_rate",
                    "origin_accounts_seen_once_rate",
                    "merchant_destination_rate",
                    "isFlaggedFraud",
                )
                if k in report
            },
            indent=2,
        ),
        "```",
        "",
        "## Leakage risks and how the pipeline handles them",
        "",
        *[f"- {note}" for note in report["leakage_notes"]],
        "",
        "## Dataset limitations",
        "",
        *[f"- {note}" for note in report["limitations"]],
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a PaySim-format CSV")
    parser.add_argument("data", type=Path)
    parser.add_argument("--data-kind", choices=["paysim", "synthetic"], required=True)
    parser.add_argument("--out", type=Path, default=Path("ml/reports"))
    args = parser.parse_args()

    df = load_paysim(args.data)
    report = inspect(df)
    report["sha256"] = file_sha256(args.data)
    report["data_kind"] = args.data_kind
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "data_inspection.json").write_text(json.dumps(report, indent=2))
    (args.out / "data_inspection.md").write_text(
        to_markdown(report, args.data.name, args.data_kind)
    )
    print(f"Wrote {args.out / 'data_inspection.md'}")


if __name__ == "__main__":
    main()
