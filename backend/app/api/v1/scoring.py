from fastapi import APIRouter, Request
from sqlalchemy import and_, exists, func, select

from app.api.deps import DbSession, SeniorUser
from app.core.errors import not_found
from app.models import RiskAssessment, Transaction
from app.schemas.common import ErrorResponse
from app.schemas.scoring import (
    RiskAssessmentRead,
    ScoreOneResult,
    ScoreRunRequest,
    ScoreRunResult,
)
from app.services.audit import record_audit
from app.services.model_registry import load_active
from app.services.scoring import score_transactions, unscored_transactions

router = APIRouter(
    prefix="/scoring",
    tags=["scoring"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse, "description": "No usable model (MODEL_NOT_AVAILABLE)"},
    },
)


@router.post(
    "/transactions/{transaction_id}",
    response_model=ScoreOneResult,
    summary="Score one transaction now (creates a new assessment)",
)
def score_one(
    transaction_id: int, user: SeniorUser, db: DbSession, request: Request
) -> ScoreOneResult:
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise not_found("Transaction", transaction_id)
    model = load_active(db)
    assessments, alerts = score_transactions(db, [tx], model)
    record_audit(
        db,
        actor=user,
        action="transaction.scored",
        entity_type="transaction",
        entity_id=tx.id,
        after={"model_version": model.version, "alerts_created": len(alerts)},
        request=request,
    )
    db.commit()
    return ScoreOneResult(
        assessment=RiskAssessmentRead.model_validate(assessments[0]),
        alert_id=alerts[0].id if alerts else None,
    )


@router.post(
    "/run",
    response_model=ScoreRunResult,
    summary="Score the oldest transactions not yet scored by the active model",
)
def score_batch(
    body: ScoreRunRequest, user: SeniorUser, db: DbSession, request: Request
) -> ScoreRunResult:
    model = load_active(db)
    batch = unscored_transactions(db, model, body.limit)
    _, alerts = score_transactions(db, batch, model)
    record_audit(
        db,
        actor=user,
        action="scoring.run",
        entity_type="model_version",
        entity_id=model.id,
        after={"scored": len(batch), "alerts_created": len(alerts)},
        request=request,
    )
    db.commit()
    remaining = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            ~exists().where(
                and_(
                    RiskAssessment.transaction_id == Transaction.id,
                    RiskAssessment.model_version_id == model.id,
                )
            )
        )
    )
    return ScoreRunResult(
        model_version=model.version,
        scored=len(batch),
        alerts_created=len(alerts),
        remaining_unscored=remaining or 0,
    )
