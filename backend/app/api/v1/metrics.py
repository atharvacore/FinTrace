"""Dashboard metrics, computed from the database (and the active model's stored evaluation)."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import Integer, and_, cast, func, select

from app.api.deps import AnalystUser, DbSession
from app.models import Alert, Case, ModelVersion, RiskAssessment, Transaction
from app.models.enums import AlertStatus, CaseStatus, RiskLevel
from app.schemas.common import ErrorResponse
from app.schemas.metrics import (
    ActiveModelSummary,
    LabelCheck,
    ModelEvaluation,
    Overview,
    RiskBin,
    RiskDistribution,
)
from app.services.model_registry import model_not_available
from app.services.scoring import OPEN_ALERT_STATUSES

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


def _active(db: DbSession) -> ModelVersion | None:
    return db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))


def _counts(db: DbSession, column, enum) -> dict[str, int]:
    rows = dict(db.execute(select(column, func.count()).group_by(column)).all())
    return {member.value: rows.get(member, 0) for member in enum}


def _latest_assessments(model_id: int):
    """Latest assessment per transaction from one model (re-scoring can add more than one)."""
    ranked = (
        select(
            RiskAssessment.transaction_id,
            RiskAssessment.risk_score,
            RiskAssessment.risk_level,
            func.row_number()
            .over(
                partition_by=RiskAssessment.transaction_id,
                order_by=(RiskAssessment.scored_at.desc(), RiskAssessment.id.desc()),
            )
            .label("rn"),
        )
        .where(RiskAssessment.model_version_id == model_id)
        .subquery()
    )
    return (
        select(ranked.c.transaction_id, ranked.c.risk_score, ranked.c.risk_level)
        .where(ranked.c.rn == 1)
        .subquery()
    )


@router.get("/overview", response_model=Overview, summary="Counts and workload for the dashboard")
def overview(user: AnalystUser, db: DbSession) -> Overview:
    model = _active(db)
    tx_total = db.scalar(select(func.count()).select_from(Transaction)) or 0
    scored = 0
    label_check = None
    if model is not None:
        latest = _latest_assessments(model.id)
        scored = db.scalar(select(func.count()).select_from(latest)) or 0
        labelled = select(
            func.count(Transaction.label_is_fraud),
            func.count().filter(Transaction.label_is_fraud.is_(True)),
            func.count().filter(
                and_(
                    Transaction.label_is_fraud.is_(True),
                    select(Alert.id).where(Alert.transaction_id == Transaction.id).exists(),
                )
            ),
        ).join(latest, latest.c.transaction_id == Transaction.id)
        with_label, fraud_scored, fraud_alerted = db.execute(labelled).one()
        alerts_with_label, alerts_fraud = db.execute(
            select(
                func.count(Transaction.label_is_fraud),
                func.count().filter(Transaction.label_is_fraud.is_(True)),
            ).join(Alert, Alert.transaction_id == Transaction.id)
        ).one()
        if with_label:
            label_check = LabelCheck(
                scored_with_label=with_label,
                labelled_fraud_scored=fraud_scored,
                labelled_fraud_alerted=fraud_alerted,
                alerts_with_label=alerts_with_label,
                alerts_labelled_fraud=alerts_fraud,
            )

    alerts_by_status = _counts(db, Alert.status, AlertStatus)
    alerts_total = sum(alerts_by_status.values())
    open_by_priority = dict(
        db.execute(
            select(Alert.priority, func.count())
            .where(Alert.status.in_(OPEN_ALERT_STATUSES))
            .group_by(Alert.priority)
        ).all()
    )
    decisions = dict(
        db.execute(
            select(Case.decision, func.count())
            .where(Case.decision.is_not(None))
            .group_by(Case.decision)
        ).all()
    )
    return Overview(
        transactions_total=tx_total,
        transactions_scored=scored,
        transactions_unscored=tx_total - scored,
        alerts_total=alerts_total,
        alerts_by_status=alerts_by_status,
        open_alerts_by_priority={lvl.value: open_by_priority.get(lvl, 0) for lvl in RiskLevel},
        alerts_per_1000_scored=round(1000 * alerts_total / scored, 2) if scored else None,
        cases_by_status=_counts(db, Case.status, CaseStatus),
        decisions={d.value: n for d, n in decisions.items()},
        my_open_alerts=db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.assignee_id == user.id, Alert.status.in_(OPEN_ALERT_STATUSES))
        )
        or 0,
        my_open_cases=db.scalar(
            select(func.count())
            .select_from(Case)
            .where(Case.assignee_id == user.id, Case.status != CaseStatus.CLOSED)
        )
        or 0,
        active_model=ActiveModelSummary.model_validate(model, from_attributes=True)
        if model
        else None,
        label_check=label_check,
    )


@router.get(
    "/risk-distribution",
    response_model=RiskDistribution,
    summary="Histogram of the active model's latest risk score per transaction",
    responses={503: {"model": ErrorResponse}},
)
def risk_distribution(
    _: AnalystUser, db: DbSession, bins: Annotated[int, Query(ge=5, le=100)] = 20
) -> RiskDistribution:
    model = _active(db)
    if model is None:
        raise model_not_available("No active model is registered.")
    latest = _latest_assessments(model.id)
    # Bucket 0..bins-1; a score of exactly 1.0 goes in the top bucket.
    bucket = func.least(cast(func.floor(latest.c.risk_score * bins), Integer), bins - 1)
    rows = db.execute(
        select(
            bucket.label("b"),
            func.count(),
            func.count().filter(Transaction.label_is_fraud.is_(True)),
        )
        .select_from(latest)
        .join(Transaction, Transaction.id == latest.c.transaction_id)
        .group_by("b")
    ).all()
    found = {b: (n, f) for b, n, f in rows}
    levels = dict(
        db.execute(select(latest.c.risk_level, func.count()).group_by(latest.c.risk_level)).all()
    )
    above = db.scalar(
        select(func.count()).select_from(latest).where(latest.c.risk_score >= model.threshold)
    )
    return RiskDistribution(
        model_version=model.version,
        threshold=model.threshold,
        transactions=sum(n for n, _ in found.values()),
        bins=[
            RiskBin(
                lower=round(i / bins, 4),
                upper=round((i + 1) / bins, 4),
                count=found.get(i, (0, 0))[0],
                labelled_fraud=found.get(i, (0, 0))[1],
            )
            for i in range(bins)
        ],
        by_level={lvl.value: levels.get(lvl, 0) for lvl in RiskLevel},
        above_threshold=above or 0,
    )


def _caveats(meta: dict, is_demo: bool) -> list[str]:
    caveats = []
    if is_demo:
        caveats.append(
            "This model was trained on the bundled synthetic sample for smoke tests. "
            "Its metrics are NOT results."
        )
    caveats.append(
        "PaySim is simulated mobile-money data. Metrics do not transfer to real payment systems."
    )
    caveats.append("Labels mark simulated fraud, not confirmed money laundering.")
    chosen = meta.get("models", {}).get(meta.get("selection", {}).get("chosen", ""), {})
    valid_p = chosen.get("validation", {}).get("prevalence")
    test_p = chosen.get("test", {}).get("prevalence")
    if valid_p and test_p and max(valid_p, test_p) > 2 * min(valid_p, test_p):
        caveats.append(
            f"Fraud prevalence differs between validation ({valid_p:.4%}) and test "
            f"({test_p:.4%}), so precision on the two splits is not directly comparable."
        )
    if meta.get("feature_set") == "strict" and meta.get("data_kind") == "paysim":
        caveats.append(
            "Near-perfect PaySim scores come mostly from a simulator signature (amount equal to "
            "the full origin balance); see docs/MODEL_REPORT.md for the run without it."
        )
    return caveats


@router.get(
    "/model-evaluation",
    response_model=ModelEvaluation,
    summary="Stored offline evaluation of the active model",
    responses={503: {"model": ErrorResponse}},
)
def model_evaluation(_: AnalystUser, db: DbSession) -> ModelEvaluation:
    model = _active(db)
    if model is None:
        raise model_not_available("No active model is registered.")
    meta = model.metrics or {}
    return ModelEvaluation(
        version=model.version,
        algorithm=model.algorithm,
        feature_set=model.feature_set,
        threshold=model.threshold,
        is_synthetic_demo=model.is_synthetic_demo,
        trained_at=model.trained_at,
        data_kind=meta.get("data_kind"),
        dataset=meta.get("dataset", {}),
        split=meta.get("split", {}),
        selection=meta.get("selection", {}),
        methodology=meta.get("methodology", []),
        models={
            name: {k: v for k, v in info.items() if k != "fit_seconds"}
            for name, info in meta.get("models", {}).items()
        },
        caveats=_caveats(meta, model.is_synthetic_demo),
    )
