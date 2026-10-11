"""Reproducible training and evaluation.

    python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --promote

Steps (each one is logged into the artifact's metadata):
1. Load and schema-check the CSV; fingerprint it with sha256.
2. Compute history counts from strictly earlier steps, then the feature matrix.
3. Split chronologically by step: train (first ~70% of rows), validation (~15%), test (last ~15%).
4. Fit a baseline (scaled logistic regression) and an improved model (histogram gradient
   boosting) on TRAIN only. Scaling lives inside the pipeline, so it is fitted on TRAIN only.
5. Pick each model's operating threshold (best F1) and alert-budget thresholds on VALIDATION.
6. Choose the model with the higher validation average precision.
7. Evaluate both models on TEST exactly once with those fixed thresholds.
8. Write model.joblib, metadata.json and report.md into a versioned folder.
"""

import argparse
import json
import platform
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from fintrace_ml import __version__
from fintrace_ml.data import LABEL, file_sha256, load_paysim
from fintrace_ml.evaluate import (
    ALERT_BUDGETS,
    best_f1_threshold,
    evaluate_split,
    threshold_for_alert_rate,
)
from fintrace_ml.features import FEATURE_SETS, add_history_counts, build_features, feature_names
from fintrace_ml.split import chronological_split

MODELS = {
    "logistic_regression": "Baseline: standardised features + class-weighted logistic regression",
    "hist_gradient_boosting": "Improved: histogram gradient boosting (scikit-learn)",
}


def make_model(name: str, seed: int) -> Pipeline | HistGradientBoostingClassifier:
    if name == "logistic_regression":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed),
                ),
            ]
        )
    if name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.08,
            max_leaf_nodes=31,
            min_samples_leaf=40,
            l2_regularization=1.0,
            early_stopping=False,  # deterministic and uses all training rows
            random_state=seed,
        )
    raise ValueError(name)


def _budget_name(rate: float) -> str:
    return f"top_{rate * 100:g}pct"


def run(
    data_path: Path,
    data_kind: str,
    out_root: Path,
    feature_set: str = "strict",
    seed: int = 42,
    nrows: int | None = None,
) -> Path:
    started = time.perf_counter()
    raw = load_paysim(data_path, nrows=nrows)
    df = add_history_counts(raw)
    X = build_features(df, feature_set)
    y = df[LABEL].to_numpy()
    train, valid, test, bounds = chronological_split(df)
    for name, mask in (("train", train), ("validation", valid), ("test", test)):
        if df.loc[mask, LABEL].nunique() < 2:
            raise ValueError(f"The {name} split has only one class; use more data")

    results: dict[str, dict] = {}
    fitted: dict[str, object] = {}
    for model_name in MODELS:
        model = make_model(model_name, seed)
        t0 = time.perf_counter()
        model.fit(X[train], y[train])
        fit_seconds = round(time.perf_counter() - t0, 1)
        valid_scores = model.predict_proba(X[valid])[:, 1]
        test_scores = model.predict_proba(X[test])[:, 1]

        threshold = best_f1_threshold(y[valid], valid_scores)
        budgets = {
            _budget_name(r): threshold_for_alert_rate(valid_scores, r) for r in ALERT_BUDGETS
        }
        results[model_name] = {
            "description": MODELS[model_name],
            "fit_seconds": fit_seconds,
            "operating_threshold": round(threshold, 6),
            "validation": evaluate_split(y[valid], valid_scores, threshold, budgets),
            "test": evaluate_split(y[test], test_scores, threshold, budgets),
        }
        fitted[model_name] = model

    chosen = max(results, key=lambda m: results[m]["validation"]["average_precision"] or 0)
    trained_at = datetime.now(UTC)
    version = f"{chosen.split('_')[0]}-{feature_set}-{data_kind}-{trained_at:%Y%m%d%H%M%S}"
    out_dir = out_root / version
    out_dir.mkdir(parents=True, exist_ok=False)

    model_path = out_dir / "model.joblib"
    joblib.dump(fitted[chosen], model_path)
    metadata = {
        "version": version,
        "algorithm": chosen,
        "feature_set": feature_set,
        "features": feature_names(feature_set),
        "threshold": results[chosen]["operating_threshold"],
        "data_kind": data_kind,
        "is_synthetic_demo": data_kind != "paysim",
        "dataset": {
            "file": data_path.name,
            "sha256": file_sha256(data_path),
            "rows_used": int(len(df)),
            "nrows_limit": nrows,
        },
        "split": {
            "method": "chronological by step; cuts between whole steps",
            "boundaries": bounds.as_dict(),
            "rows": {"train": int(train.sum()), "valid": int(valid.sum()), "test": int(test.sum())},
        },
        "methodology": [
            "History counts use strictly earlier steps only.",
            "All preprocessing is fitted on the training split only (inside the model pipeline).",
            "Thresholds (best-F1 and alert budgets) are chosen on validation, then fixed.",
            "The deployed model is the one with the higher validation average precision.",
            "Test metrics are computed once, after all choices were made.",
        ],
        "selection": {"metric": "validation average_precision", "chosen": chosen},
        "models": results,
        "artifact_sha256": file_sha256(model_path),
        "trained_at": trained_at.isoformat(),
        "seed": seed,
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "fintrace_ml": __version__,
        },
        "runtime_seconds": round(time.perf_counter() - started, 1),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (out_dir / "report.md").write_text(render_report(metadata))
    return out_dir


def _row(name: str, split: dict) -> str:
    op = split["at_operating_threshold"]
    cm = op["confusion_matrix"]
    return (
        f"| {name} | {split['average_precision']} | {split['roc_auc']} | {op['precision']} | "
        f"{op['recall']} | {op['f1']} | {cm['tp']} / {cm['fp']} / {cm['fn']} / {cm['tn']} | "
        f"{op['alerts_per_1000']} |"
    )


def render_report(meta: dict) -> str:
    lines = [f"# Model Report: `{meta['version']}`", ""]
    if meta["is_synthetic_demo"]:
        lines += [
            "> **SMOKE TEST ON SYNTHETIC DATA. THESE ARE NOT RESULTS.** The data came from "
            "`scripts/generate_sample_data.py`, a short rule-based generator. The numbers only "
            "show that the pipeline runs end to end.",
            "",
        ]
    split = meta["split"]
    lines += [
        f"- Data: `{meta['dataset']['file']}` ({meta['data_kind']}), "
        f"{meta['dataset']['rows_used']:,} rows, sha256 `{meta['dataset']['sha256'][:16]}…`",
        f"- Features: `{meta['feature_set']}` ({len(meta['features'])} features)",
        f"- Split: {split['method']}; train ≤ step {split['boundaries']['train_last_step']} "
        f"({split['rows']['train']:,} rows), validation ≤ {split['boundaries']['valid_last_step']} "
        f"({split['rows']['valid']:,}), test ≤ {split['boundaries']['test_last_step']} "
        f"({split['rows']['test']:,})",
        f"- Chosen model: **{meta['algorithm']}** ({meta['selection']['metric']}), "
        f"operating threshold {meta['threshold']}",
        f"- Trained {meta['trained_at']} with seed {meta['seed']}, scikit-learn "
        f"{meta['environment']['scikit_learn']}",
        "",
        "## Test-split results (thresholds fixed on validation)",
        "",
        "Average precision of a random model equals the prevalence "
        f"({meta['models'][meta['algorithm']]['test']['prevalence']}).",
        "",
        "| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | "
        "Alerts per 1,000 |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for name, res in meta["models"].items():
        lines.append(_row(name, res["test"]))
    lines += [
        "",
        "## Alert-budget trade-off on test (chosen model)",
        "",
        "Each budget's threshold was set on validation so that the given share of transactions "
        "would alert; the table shows what that threshold does on the later test period.",
        "",
        "| Budget | Threshold | Alerts per 1,000 | Precision | Recall | FP per TP |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for budget, m in meta["models"][meta["algorithm"]]["test"]["at_alert_budgets"].items():
        lines.append(
            f"| {budget} | {m['threshold']} | {m['alerts_per_1000']} | {m['precision']} | "
            f"{m['recall']} | {m['false_positives_per_true_positive']} |"
        )
    lines += [
        "",
        "## Validation results (used for all choices)",
        "",
        "| Model | Avg precision | ROC AUC | Precision | Recall | F1 | TP / FP / FN / TN | "
        "Alerts per 1,000 |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for name, res in meta["models"].items():
        lines.append(_row(name, res["validation"]))
    lines += [
        "",
        "## Methodology",
        "",
        *[f"- {m}" for m in meta["methodology"]],
        "",
        "## Responsible-use note",
        "",
        "Scores are triage signals for human review. PaySim labels are simulated fraud, not "
        "confirmed money laundering. This model is not validated for real-world decisions.",
        "",
    ]
    return "\n".join(lines)


def promote(out_dir: Path, current: Path) -> None:
    """Copy a trained artifact to the folder the API loads (FINTRACE_MODEL_DIR)."""
    if current.exists():
        shutil.rmtree(current)
    shutil.copytree(out_dir, current)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate FinTrace models")
    parser.add_argument("data", type=Path, help="PaySim-format CSV")
    parser.add_argument(
        "--data-kind",
        choices=["paysim", "synthetic"],
        required=True,
        help="Recorded in the artifact; 'synthetic' marks every report as a smoke test",
    )
    parser.add_argument("--feature-set", choices=FEATURE_SETS, default="strict")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--nrows", type=int, default=None, help="Use only the first N rows")
    parser.add_argument("--out", type=Path, default=Path("ml/artifacts"))
    parser.add_argument(
        "--promote", action="store_true", help="Also copy the artifact to <out>/current"
    )
    args = parser.parse_args()

    out_dir = run(args.data, args.data_kind, args.out, args.feature_set, args.seed, args.nrows)
    print(f"Artifact written to {out_dir}")
    print((out_dir / "report.md").read_text())
    if args.promote:
        promote(out_dir, args.out / "current")
        print(f"Promoted to {args.out / 'current'}")


if __name__ == "__main__":
    main()
