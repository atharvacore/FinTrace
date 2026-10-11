import json

import pytest

from fintrace_ml import train as train_module
from fintrace_ml.data import DataError, load_paysim
from fintrace_ml.inspect_data import inspect, to_markdown


def test_load_rejects_missing_file_and_columns(tmp_path):
    with pytest.raises(DataError, match="Download PaySim"):
        load_paysim(tmp_path / "nope.csv")
    bad = tmp_path / "bad.csv"
    bad.write_text("step,type,amount\n1,PAYMENT,10\n")
    with pytest.raises(DataError, match="missing required columns"):
        load_paysim(bad)


def test_load_rejects_unknown_type(tmp_path, sample_csv):
    lines = sample_csv.read_text().splitlines()
    lines[1] = lines[1].replace("CASH_OUT", "WIRE", 1).replace("PAYMENT", "WIRE", 1)
    path = tmp_path / "x.csv"
    path.write_text("\n".join(lines))
    with pytest.raises(DataError, match="Unknown transaction types"):
        load_paysim(path)


def test_inspection_reports_imbalance_split_and_leakage(sample_csv):
    report = inspect(load_paysim(sample_csv))
    assert report["rows"] == 5000 and report["frauds"] == 108
    assert sum(report["missing_values"].values()) == 0
    split = report["chronological_split"]
    assert split["train"]["rows"] + split["valid"]["rows"] + split["test"]["rows"] == 5000
    assert any("isFlaggedFraud" in note for note in report["leakage_notes"])
    report["sha256"] = "0" * 64
    assert "SYNTHETIC SAMPLE, NOT PAYSIM" in to_markdown(report, "s.csv", "synthetic")
    assert "SYNTHETIC SAMPLE" not in to_markdown(report, "p.csv", "paysim")


@pytest.fixture(scope="module")
def artifact(tmp_path_factory):
    from tests.conftest import SAMPLE_CSV

    out = tmp_path_factory.mktemp("artifacts")
    return train_module.run(SAMPLE_CSV, "synthetic", out, seed=7)


def test_training_writes_complete_versioned_artifact(artifact):
    assert {p.name for p in artifact.iterdir()} == {"model.joblib", "metadata.json", "report.md"}
    meta = json.loads((artifact / "metadata.json").read_text())
    assert meta["version"] == artifact.name
    assert meta["is_synthetic_demo"] is True
    assert meta["algorithm"] in train_module.MODELS
    assert set(meta["models"]) == set(train_module.MODELS)
    assert 0 < meta["threshold"] < 1
    assert len(meta["artifact_sha256"]) == 64 and len(meta["dataset"]["sha256"]) == 64
    test = meta["models"][meta["algorithm"]]["test"]
    for key in ("average_precision", "roc_auc", "prevalence", "at_operating_threshold",
                "at_alert_budgets"):  # fmt: skip
        assert key in test
    assert "confusion_matrix" in test["at_operating_threshold"]
    report = (artifact / "report.md").read_text()
    assert "THESE ARE NOT RESULTS" in report


def test_same_seed_gives_identical_metrics(artifact, tmp_path):
    from tests.conftest import SAMPLE_CSV

    again = train_module.run(SAMPLE_CSV, "synthetic", tmp_path, seed=7)
    first = json.loads((artifact / "metadata.json").read_text())["models"]
    second = json.loads((again / "metadata.json").read_text())["models"]
    for m in (first, second):
        for res in m.values():
            res.pop("fit_seconds")
    assert first == second


def test_models_are_fitted_on_training_rows_only(monkeypatch, tmp_path, sample_csv):
    """Spy on fit(): every row a model sees must come from the training period."""
    seen_steps: list = []
    real_make_model = train_module.make_model

    class Spy:
        def __init__(self, inner):
            self.inner = inner

        def fit(self, X, y):
            seen_steps.append(X.index)
            return self.inner.fit(X, y)

        def predict_proba(self, X):
            return self.inner.predict_proba(X)

    monkeypatch.setattr(train_module, "make_model", lambda n, s: Spy(real_make_model(n, s)))
    monkeypatch.setattr(train_module.joblib, "dump", lambda obj, path: path.write_bytes(b"x"))
    out = train_module.run(sample_csv, "synthetic", tmp_path, seed=1)
    meta = json.loads((out / "metadata.json").read_text())
    df = load_paysim(sample_csv)
    train_last = meta["split"]["boundaries"]["train_last_step"]
    assert len(seen_steps) == 2
    for index in seen_steps:
        assert df.loc[index, "step"].max() <= train_last
        assert len(index) == meta["split"]["rows"]["train"]


def test_scaler_statistics_come_from_training_rows(sample_csv):
    import numpy as np

    from fintrace_ml.features import add_history_counts, build_features
    from fintrace_ml.split import chronological_split

    df = add_history_counts(load_paysim(sample_csv))
    X = build_features(df)
    train, *_ = chronological_split(df)
    model = train_module.make_model("logistic_regression", 0)
    model.fit(X[train], df.loc[train, "isFraud"])
    np.testing.assert_allclose(model.named_steps["scale"].mean_, X[train].mean().to_numpy())
    assert not np.allclose(model.named_steps["scale"].mean_, X.mean().to_numpy())


def test_promote_copies_artifact(artifact, tmp_path):
    current = tmp_path / "current"
    current.mkdir()
    (current / "stale.txt").write_text("old")
    train_module.promote(artifact, current)
    assert (current / "metadata.json").exists() and not (current / "stale.txt").exists()
