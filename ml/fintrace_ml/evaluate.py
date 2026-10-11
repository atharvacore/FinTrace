"""Metrics for imbalanced fraud classification, focused on analyst workload."""

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

# Alert budgets: what fraction of all transactions the review team can look at.
ALERT_BUDGETS = (0.001, 0.005, 0.01, 0.02)


def best_f1_threshold(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Threshold that maximises F1. Call this on VALIDATION data only."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-12, None)
    # precision/recall have one more element than thresholds; drop the final (recall=0) point
    best = int(np.nanargmax(f1[:-1]))
    return float(thresholds[best])


def threshold_for_alert_rate(scores: np.ndarray, rate: float) -> float:
    """Score above which roughly `rate` of transactions would alert. VALIDATION data only."""
    return float(np.quantile(scores, 1 - rate))


def metrics_at_threshold(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    y_pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    n = len(y_true)
    return {
        "threshold": round(float(threshold), 6),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "alerts": int(tp + fp),
        "alerts_per_1000": round(1000 * (tp + fp) / n, 3),
        "false_positives_per_1000": round(1000 * fp / n, 3),
        "false_positives_per_true_positive": round(float(fp / tp), 2) if tp else None,
    }


def ranking_metrics(y_true: np.ndarray, scores: np.ndarray) -> dict:
    has_both = len(np.unique(y_true)) == 2
    return {
        "rows": int(len(y_true)),
        "positives": int(y_true.sum()),
        "prevalence": round(float(y_true.mean()), 6),
        # A random model's average precision equals the prevalence: the honest baseline.
        "average_precision": round(float(average_precision_score(y_true, scores)), 4)
        if has_both
        else None,
        "roc_auc": round(float(roc_auc_score(y_true, scores)), 4) if has_both else None,
    }


def evaluate_split(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    budget_thresholds: dict[str, float],
) -> dict:
    """Evaluate one split with thresholds that were chosen elsewhere (on validation)."""
    return {
        **ranking_metrics(y_true, scores),
        "at_operating_threshold": metrics_at_threshold(y_true, scores, threshold),
        "at_alert_budgets": {
            name: metrics_at_threshold(y_true, scores, t) for name, t in budget_thresholds.items()
        },
    }
