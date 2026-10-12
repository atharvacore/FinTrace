import json
import shutil

import numpy as np
import pytest
from sqlalchemy import func, select

from app.models import Alert, AuditEvent, RiskAssessment
from app.models.enums import RiskLevel, Role
from app.services.scoring import model_level
from tests.conftest import SAMPLE_CSV


@pytest.fixture
def admin(make_user, login):
    return login(make_user(Role.ADMIN))


@pytest.fixture
def senior(make_user, login):
    return login(make_user(Role.SENIOR_ANALYST))


@pytest.fixture
def analyst(make_user, login):
    return login(make_user(Role.ANALYST))


# ---------------------------------------------------------------- no model


def test_scoring_without_a_model_is_503_with_instructions(client, senior, imported_sample):
    for resp in (
        client.post("/api/v1/scoring/transactions/1", headers=senior),
        client.post("/api/v1/scoring/run", json={}, headers=senior),
    ):
        assert resp.status_code == 503
        error = resp.json()["error"]
        assert error["code"] == "MODEL_NOT_AVAILABLE"
        assert "fintrace_ml.train" in error["message"]
        assert "/api/v1/models/sync" in error["message"]


def test_no_assessment_is_written_without_a_model(client, senior, imported_sample, db):
    client.post("/api/v1/scoring/run", json={}, headers=senior)
    assert db.scalar(select(func.count()).select_from(RiskAssessment)) == 0


def test_sync_without_promoted_artifact_is_503(client, admin):
    resp = client.post("/api/v1/models/sync", headers=admin)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODEL_NOT_AVAILABLE"


def test_active_model_endpoint_is_503_when_none(client, analyst):
    assert client.get("/api/v1/models/active", headers=analyst).status_code == 503


# ---------------------------------------------------------------- registry


@pytest.mark.usefixtures("promoted")
@pytest.mark.parametrize("role", [Role.ANALYST, Role.SENIOR_ANALYST])
def test_only_admin_can_sync_models(client, make_user, login, role):
    assert client.post("/api/v1/models/sync", headers=login(make_user(role))).status_code == 403


@pytest.mark.usefixtures("promoted")
def test_sync_registers_activates_and_audits(client, admin, analyst, db):
    resp = client.post("/api/v1/models/sync", headers=admin)
    assert resp.status_code == 200, resp.text
    model = resp.json()
    assert model["is_active"] is True and model["is_synthetic_demo"] is True
    again = client.post("/api/v1/models/sync", headers=admin).json()
    assert again["id"] == model["id"]

    actions = db.scalars(select(AuditEvent.action).order_by(AuditEvent.id)).all()
    assert actions == ["model.registered", "model.activated"]

    active = client.get("/api/v1/models/active", headers=analyst).json()
    assert active["version"] == model["version"]
    assert "test" in active["metrics"]["models"][active["algorithm"]]

    ready = client.get("/api/v1/health/ready").json()["model"]
    assert ready["status"] == "ok" and "SYNTHETIC" in ready["detail"]


def test_tampered_artifact_is_refused(client, admin, promoted):
    with (promoted / "model.joblib").open("ab") as fh:
        fh.write(b"tampered")
    resp = client.post("/api/v1/models/sync", headers=admin)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MODEL_ARTIFACT_MODIFIED"


def test_activate_switches_versions(client, admin, promoted, tmp_path, db):
    from fintrace_ml.train import run

    first = client.post("/api/v1/models/sync", headers=admin).json()
    other = run(SAMPLE_CSV, "synthetic", tmp_path / "other", "no_origin_balance", seed=3)
    shutil.rmtree(promoted)
    shutil.copytree(other, promoted)
    second = client.post("/api/v1/models/sync", headers=admin).json()
    assert second["id"] != first["id"]

    resp = client.post(f"/api/v1/models/{first['id']}/activate", headers=admin)
    assert resp.status_code == 200 and resp.json()["is_active"] is True
    listing = {m["id"]: m["is_active"] for m in client.get("/api/v1/models", headers=admin).json()}
    assert listing == {first["id"]: True, second["id"]: False}
    assert client.post("/api/v1/models/999/activate", headers=admin).status_code == 404


# ---------------------------------------------------------------- scoring


def test_model_level_is_relative_to_threshold():
    assert model_level(0.95, 0.9) == RiskLevel.CRITICAL
    assert model_level(0.91, 0.9) == RiskLevel.HIGH
    assert model_level(0.5, 0.9) == RiskLevel.MEDIUM
    assert model_level(0.1, 0.9) == RiskLevel.LOW


@pytest.mark.usefixtures("imported_sample")
def test_online_scores_match_offline_pipeline(client, senior, active_model, synthetic_artifact, db):
    """The API must compute exactly the features and scores the training pipeline would."""
    import joblib
    from fintrace_ml.data import load_paysim
    from fintrace_ml.features import add_history_counts, build_features

    resp = client.post("/api/v1/scoring/run", json={"limit": 5000}, headers=senior)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scored"] == 5000 and body["remaining_unscored"] == 0

    df = add_history_counts(load_paysim(SAMPLE_CSV))
    estimator = joblib.load(synthetic_artifact / "model.joblib")
    offline = estimator.predict_proba(build_features(df, active_model.feature_set))[:, 1]
    # The sample is imported in file order, so transaction id N is CSV row N.
    online = np.array(
        [
            float(score)
            for score in db.scalars(
                select(RiskAssessment.risk_score).order_by(RiskAssessment.transaction_id)
            )
        ]
    )
    np.testing.assert_allclose(online, offline, atol=1e-5)


@pytest.mark.usefixtures("imported_sample", "active_model")
def test_assessment_is_persisted_with_version_time_score_and_reasons(client, senior, db):
    meta_threshold = None
    resp = client.post("/api/v1/scoring/run", json={"limit": 5000}, headers=senior).json()
    assert resp["alerts_created"] > 0
    assessments = db.scalars(select(RiskAssessment)).all()
    for a in assessments:
        assert a.model_version_id and a.scored_at is not None
        assert 0 <= float(a.risk_score) <= 1
    flagged = [a for a in assessments if "MODEL_SCORE_ABOVE_THRESHOLD" in a.reason_codes]
    assert flagged
    meta_threshold = float(flagged[0].model.threshold)
    assert all(float(a.risk_score) >= meta_threshold for a in flagged)
    assert all(a.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) for a in flagged)
    alerted = set(db.scalars(select(Alert.transaction_id)))
    assert {a.transaction_id for a in flagged} <= alerted


@pytest.mark.usefixtures("imported_sample", "active_model")
def test_rescoring_adds_assessment_but_not_a_duplicate_alert(client, senior, db):
    alerts_before = None
    for _ in range(2):
        resp = client.post("/api/v1/scoring/transactions/1", headers=senior)
        assert resp.status_code == 200
        alerts_before = alerts_before if alerts_before is not None else resp.json()["alert_id"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(RiskAssessment)
            .where(RiskAssessment.transaction_id == 1)
        )
        == 2
    )
    count = db.scalar(select(func.count()).select_from(Alert).where(Alert.transaction_id == 1))
    assert count == (1 if alerts_before else 0)


@pytest.mark.usefixtures("imported_sample", "active_model")
def test_scoring_requires_senior_role_and_existing_transaction(client, analyst, senior):
    assert client.post("/api/v1/scoring/run", json={}, headers=analyst).status_code == 403
    assert client.post("/api/v1/scoring/transactions/999999", headers=senior).status_code == 404
    assert (
        client.post("/api/v1/scoring/run", json={"limit": 9999}, headers=senior).status_code == 422
    )


@pytest.mark.usefixtures("imported_sample", "active_model")
def test_transaction_views_show_scores_alerts_and_history(client, senior, analyst):
    client.post("/api/v1/scoring/run", json={"limit": 5000}, headers=senior)
    high = client.get(
        "/api/v1/transactions?risk_level=high&risk_level=critical&page_size=200", headers=analyst
    ).json()
    assert high["total"] > 0
    assert all(i["risk_level"] in ("high", "critical") for i in high["items"])
    with_alert = client.get("/api/v1/transactions?has_open_alert=true", headers=analyst).json()
    without = client.get("/api/v1/transactions?has_open_alert=false", headers=analyst).json()
    assert with_alert["total"] + without["total"] == 5000
    assert all(i["has_open_alert"] for i in with_alert["items"])

    tx_id = with_alert["items"][0]["id"]
    detail = client.get(f"/api/v1/transactions/{tx_id}", headers=analyst).json()
    assert len(detail["assessments"]) == 1 and len(detail["alerts"]) == 1
    assert detail["assessments"][0]["model_version"]
    assert json.dumps(detail)  # serialisable


def test_scoring_is_audited(client, senior, imported_sample, active_model, db):
    client.post("/api/v1/scoring/run", json={"limit": 10}, headers=senior)
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "scoring.run"))
    assert event.after["scored"] == 10


@pytest.mark.parametrize(
    ("field", "value"),
    [("version", "."), ("version", ".."), ("version", ""), ("version", 7), ("threshold", 0.999999)],
)
def test_unsafe_artifact_metadata_is_refused(client, admin, promoted, field, value):
    import json

    meta_path = promoted / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta[field] = value
    meta_path.write_text(json.dumps(meta))
    resp = client.post("/api/v1/models/sync", headers=admin)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_MODEL_ARTIFACT"


def test_resync_restores_a_missing_registry_copy(client, admin, promoted, senior, imported_sample):
    from app.core.config import get_settings

    version = client.post("/api/v1/models/sync", headers=admin).json()["version"]
    shutil.rmtree(get_settings().model_registry_dir / version)
    assert client.post("/api/v1/models/sync", headers=admin).status_code == 200
    assert (get_settings().model_registry_dir / version / "model.joblib").is_file()
    resp = client.post("/api/v1/scoring/run", json={"limit": 10}, headers=senior)
    assert resp.status_code == 200
