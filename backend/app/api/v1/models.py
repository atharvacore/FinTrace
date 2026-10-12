from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import AdminUser, AnalystUser, DbSession
from app.core.errors import not_found
from app.models import ModelVersion
from app.schemas.common import ErrorResponse
from app.schemas.scoring import ModelVersionDetail, ModelVersionRead
from app.services import model_registry
from app.services.audit import record_audit

router = APIRouter(
    prefix="/models",
    tags=["models"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


@router.get("", response_model=list[ModelVersionRead], summary="Registered model versions")
def list_models(_: AnalystUser, db: DbSession) -> list[ModelVersion]:
    return list(db.scalars(select(ModelVersion).order_by(ModelVersion.registered_at.desc())))


@router.get(
    "/active",
    response_model=ModelVersionDetail,
    summary="The model currently used for scoring, with its evaluation",
    responses={503: {"model": ErrorResponse}},
)
def active_model(_: AnalystUser, db: DbSession) -> ModelVersion:
    row = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    if row is None:
        raise model_registry.model_not_available("No active model is registered.")
    return row


@router.post(
    "/sync",
    response_model=ModelVersionRead,
    summary="Register and activate the artifact written by `fintrace_ml.train --promote`",
    responses={409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def sync_model(admin: AdminUser, db: DbSession, request: Request) -> ModelVersion:
    previous = db.scalar(select(ModelVersion.version).where(ModelVersion.is_active.is_(True)))
    model, created = model_registry.sync_from_promoted(db)
    record_audit(
        db,
        actor=admin,
        action="model.registered" if created else "model.activated",
        entity_type="model_version",
        entity_id=model.id,
        before={"active_version": previous},
        after={"active_version": model.version, "is_synthetic_demo": model.is_synthetic_demo},
        request=request,
    )
    db.commit()
    return model


@router.post(
    "/{model_id}/activate",
    response_model=ModelVersionRead,
    summary="Switch scoring to another registered version",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def activate_model(
    model_id: int, admin: AdminUser, db: DbSession, request: Request
) -> ModelVersion:
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise not_found("Model version", model_id)
    previous = db.scalar(select(ModelVersion.version).where(ModelVersion.is_active.is_(True)))
    model_registry.activate(db, model)
    record_audit(
        db,
        actor=admin,
        action="model.activated",
        entity_type="model_version",
        entity_id=model.id,
        before={"active_version": previous},
        after={"active_version": model.version},
        request=request,
    )
    db.commit()
    return model


@router.get("/{model_id}", response_model=ModelVersionDetail, summary="One model version")
def get_model(model_id: int, _: AnalystUser, db: DbSession) -> ModelVersion:
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise not_found("Model version", model_id)
    return model
