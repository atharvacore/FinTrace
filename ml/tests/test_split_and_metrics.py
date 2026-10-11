import numpy as np
import pandas as pd
import pytest

from fintrace_ml.evaluate import (
    best_f1_threshold,
    metrics_at_threshold,
    ranking_metrics,
    threshold_for_alert_rate,
)
from fintrace_ml.split import chronological_split


def test_split_is_chronological_with_no_shared_steps():
    df = pd.DataFrame({"step": np.repeat(np.arange(1, 101), 10)})
    train, valid, test, b = chronological_split(df)
    assert (train | valid | test).all()
    assert not (train & valid).any() and not (valid & test).any()
    assert df.loc[train, "step"].max() < df.loc[valid, "step"].min()
    assert df.loc[valid, "step"].max() < df.loc[test, "step"].min()
    assert b.train_last_step == 70 and b.valid_last_step == 85 and b.test_last_step == 100


def test_split_needs_enough_steps():
    with pytest.raises(ValueError):
        chronological_split(pd.DataFrame({"step": [1, 1, 1, 2]}))


def test_metrics_at_threshold_known_values():
    y = np.array([0, 0, 0, 0, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.8, 0.9, 0.4])
    m = metrics_at_threshold(y, s, 0.5)
    assert m["confusion_matrix"] == {"tn": 3, "fp": 1, "fn": 1, "tp": 1}
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert m["alerts_per_1000"] == pytest.approx(1000 * 2 / 6, abs=1e-3)
    assert m["false_positives_per_true_positive"] == 1.0


def test_ranking_metrics_report_prevalence_baseline():
    y = np.array([0, 1, 0, 1])
    r = ranking_metrics(y, np.array([0.1, 0.9, 0.2, 0.8]))
    assert r["prevalence"] == 0.5 and r["average_precision"] == 1.0


def test_threshold_helpers():
    y = np.array([0, 0, 1, 1])
    s = np.array([0.1, 0.4, 0.35, 0.8])
    assert best_f1_threshold(y, s) in {0.35, 0.8}
    scores = np.linspace(0, 1, 1001)
    assert threshold_for_alert_rate(scores, 0.01) == pytest.approx(0.99)
