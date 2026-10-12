"""Model registry: register trained artifacts, choose the active one, load it for scoring.

Flow:
1. `python -m fintrace_ml.train ... --promote` writes an artifact to FINTRACE_MODEL_DIR.
2. An admin calls `POST /api/v1/models/sync` (or `python -m app.cli sync-model`). The artifact's
   hash is verified, it is copied to FINTRACE_MODEL_REGISTRY_DIR/<version>, recorded in
   `model_versions` and made active.
3. Scoring loads the active version from the registry folder, re-checking the hash, and caches it.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import ModelVersion

TRAIN_COMMAND = "python -m fintrace_ml.train data/raw/paysim.csv --data-kind paysim --promote"
REQUIRED_METADATA = ("version", "algorithm", "feature_set", "features", "threshold",
                     "artifact_sha256", "dataset", "trained_at", "models")  # fmt: skip


def model_not_available(detail: str) -> AppError:
    return AppError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "MODEL_NOT_AVAILABLE",
        f"{detail} Transactions cannot be scored until a model is registered. "
        f"Train one with `{TRAIN_COMMAND}`, then register it with `POST /api/v1/models/sync` "
        "(admin) or `python -m app.cli sync-model`.",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_artifact(folder: Path) -> dict[str, Any]:
    """Read and verify an artifact folder; return its metadata."""
    meta_path, model_path = folder / "metadata.json", folder / "model.joblib"
    if not meta_path.is_file() or not model_path.is_file():
        raise model_not_available(f"No model artifact found in {folder}.")
    try:
        meta = json.loads(meta_path.read_text())
    except json.JSONDecodeError:
        raise AppError(422, "INVALID_MODEL_ARTIFACT", f"{meta_path} is not valid JSON") from None
    missing = [k for k in REQUIRED_METADATA if k not in meta]
    if missing:
        raise AppError(
            422, "INVALID_MODEL_ARTIFACT", f"metadata.json is missing: {', '.join(missing)}"
        )
    if _sha256(model_path) != meta["artifact_sha256"]:
        raise AppError(
            409,
            "MODEL_ARTIFACT_MODIFIED",
            f"model.joblib in {folder} does not match the hash in its metadata. "
            "Re-run training instead of editing artifacts by hand.",
        )
    return meta


def _activate(db: Session, model: ModelVersion) -> None:
    db.execute(update(ModelVersion).where(ModelVersion.id != model.id).values(is_active=False))
    db.flush()
    model.is_active = True


def sync_from_promoted(db: Session) -> tuple[ModelVersion, bool]:
    """Register (if new) and activate the artifact in FINTRACE_MODEL_DIR.

    Returns (model_version, created). Caller commits and audits.
    """
    settings = get_settings()
    meta = read_artifact(settings.model_dir)
    version = meta["version"]
    if not all(c.isalnum() or c in "-_." for c in version):
        raise AppError(422, "INVALID_MODEL_ARTIFACT", "Unsafe characters in model version")

    existing = db.scalar(select(ModelVersion).where(ModelVersion.version == version))
    if existing is not None:
        if existing.artifact_sha256 != meta["artifact_sha256"]:
            raise AppError(
                409,
                "MODEL_VERSION_CONFLICT",
                f"Version {version} is already registered with a different artifact",
            )
        _activate(db, existing)
        return existing, False

    target = settings.model_registry_dir / version
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(settings.model_dir, target)
    model = ModelVersion(
        version=version,
        algorithm=meta["algorithm"],
        artifact_path=version,  # relative to FINTRACE_MODEL_REGISTRY_DIR
        artifact_sha256=meta["artifact_sha256"],
        feature_set=meta["feature_set"],
        threshold=Decimal(str(meta["threshold"])),
        metrics=meta,
        dataset_fingerprint=meta["dataset"]["sha256"],
        trained_at=datetime.fromisoformat(meta["trained_at"]),
        is_synthetic_demo=bool(meta.get("is_synthetic_demo", False)),
        is_active=False,
    )
    db.add(model)
    db.flush()
    _activate(db, model)
    return model, True


def activate(db: Session, model: ModelVersion) -> None:
    """Make a registered version active after checking its files are still intact."""
    read_artifact(get_settings().model_registry_dir / model.artifact_path)
    _activate(db, model)


@dataclass(frozen=True)
class LoadedModel:
    id: int
    version: str
    feature_set: str
    features: list[str]
    threshold: float
    estimator: Any


_cache: dict[tuple[int, str], LoadedModel] = {}
_cache_lock = Lock()


def load_active(db: Session) -> LoadedModel:
    """Return the active model, or raise 503 MODEL_NOT_AVAILABLE. Never invents a score."""
    row = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    if row is None:
        raise model_not_available("No active model is registered.")
    key = (row.id, row.artifact_sha256)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
        folder = get_settings().model_registry_dir / row.artifact_path
        meta = read_artifact(folder)
        loaded = LoadedModel(
            id=row.id,
            version=row.version,
            feature_set=row.feature_set,
            features=list(meta["features"]),
            threshold=float(row.threshold),
            estimator=joblib.load(folder / "model.joblib"),  # trusted: hash verified above
        )
        _cache.clear()
        _cache[key] = loaded
        return loaded
