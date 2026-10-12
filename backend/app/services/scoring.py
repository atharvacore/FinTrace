"""Online scoring: rules + the active model -> persisted risk assessment (+ alert when warranted).

Features are computed by `fintrace_ml.features.build_features`, the same function used in
training. The only difference online is where the history counts come from: here they are
counted in the database (strictly earlier steps), offline they are counted in the CSV.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd
from fintrace_ml.features import build_features, risk_indicators
from sqlalchemy import and_, exists, func, select, text
from sqlalchemy.orm import Session, aliased

from app.models import Alert, MonitoringRule, RiskAssessment, Transaction
from app.models.enums import AlertStatus, RiskLevel
from app.services.model_registry import LoadedModel
from app.services.rules import TxFacts, evaluate_rule, max_velocity_window

LEVEL_ORDER = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
ALERTING_RULE_SEVERITIES = {RiskLevel.HIGH, RiskLevel.CRITICAL}
OPEN_ALERT_STATUSES = {AlertStatus.OPEN, AlertStatus.IN_REVIEW, AlertStatus.ESCALATED}
MAX_BATCH = 5000


def model_level(score: float, threshold: float) -> RiskLevel:
    """Map a model score to a level relative to the operating threshold chosen on validation."""
    if score >= threshold:
        return RiskLevel.CRITICAL if score >= threshold + (1 - threshold) / 2 else RiskLevel.HIGH
    if score >= threshold / 2:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _max_level(levels: Sequence[RiskLevel]) -> RiskLevel:
    return max(levels, key=LEVEL_ORDER.index)


@dataclass
class _History:
    origin_prior_tx: int
    dest_prior_in: int
    origin_recent: int


def _history_counts(db: Session, ids: list[int], window: int) -> dict[int, _History]:
    """Counts of strictly earlier transactions, computed in one query for the whole batch."""
    t = aliased(Transaction)
    o = aliased(Transaction)
    d = aliased(Transaction)
    v = aliased(Transaction)
    origin_prior = (
        select(func.count())
        .where(o.origin_account == t.origin_account, o.step < t.step)
        .scalar_subquery()
    )
    dest_prior = (
        select(func.count()).where(d.dest_account == t.dest_account, d.step < t.step)
    ).scalar_subquery()
    recent = (
        select(func.count()).where(
            v.origin_account == t.origin_account, v.step < t.step, v.step >= t.step - window
        )
    ).scalar_subquery()
    rows = db.execute(select(t.id, origin_prior, dest_prior, recent).where(t.id.in_(ids)))
    return {r[0]: _History(r[1], r[2], r[3]) for r in rows}


def paysim_row(tx: Transaction, history: _History) -> dict:
    """The transaction in PaySim column names, as the shared feature code expects."""
    return {
        "step": tx.step,
        "type": tx.type.value,
        "amount": float(tx.amount),
        "nameOrig": tx.origin_account,
        "oldbalanceOrg": float(tx.origin_balance_before),
        "newbalanceOrig": float(tx.origin_balance_after),
        "nameDest": tx.dest_account,
        "oldbalanceDest": float(tx.dest_balance_before),
        "newbalanceDest": float(tx.dest_balance_after),
        "origin_prior_tx": history.origin_prior_tx,
        "dest_prior_in": history.dest_prior_in,
    }


def score_transactions(
    db: Session, transactions: Sequence[Transaction], model: LoadedModel
) -> tuple[list[RiskAssessment], list[Alert]]:
    """Score a batch, persist one assessment per transaction, create alerts. Caller commits."""
    if not transactions:
        return [], []
    lock_scoring(db)
    rules = db.scalars(
        select(MonitoringRule).where(MonitoringRule.enabled.is_(True)).order_by(MonitoringRule.id)
    ).all()
    window = max_velocity_window(rules)
    history = _history_counts(db, [tx.id for tx in transactions], window)

    rows = [paysim_row(tx, history[tx.id]) for tx in transactions]
    features = build_features(pd.DataFrame(rows), model.feature_set)
    if list(features.columns) != model.features:
        raise RuntimeError("Feature columns differ from the ones the model was trained with")
    scores = model.estimator.predict_proba(features)[:, 1]

    already_alerted = set(
        db.scalars(
            select(Alert.transaction_id).where(
                Alert.transaction_id.in_([tx.id for tx in transactions]),
                Alert.status.in_(OPEN_ALERT_STATUSES),
            )
        )
    )

    assessments: list[RiskAssessment] = []
    alerts: list[Alert] = []
    for tx, row, raw_score in zip(transactions, rows, scores, strict=True):
        raw = float(raw_score)
        score = round(raw, 5)  # stored precision; decisions use the raw score
        h = history[tx.id]
        facts = TxFacts(
            type=tx.type,
            amount=tx.amount,
            origin_balance_before=tx.origin_balance_before,
            dest_account=tx.dest_account,
            dest_prior_in=h.dest_prior_in,
            origin_recent_count=h.origin_recent,
        )
        hits = []
        for rule in rules:
            detail = evaluate_rule(rule.rule_type, rule.parameters, facts)
            if detail:
                hits.append(
                    {
                        "code": rule.code,
                        "name": rule.name,
                        "severity": rule.severity.value,
                        "detail": detail,
                    }
                )

        above = raw >= model.threshold
        level = _max_level(
            [model_level(raw, model.threshold), *(RiskLevel(hit["severity"]) for hit in hits)]
        )
        reasons = (["MODEL_SCORE_ABOVE_THRESHOLD"] if above else []) + [
            f"RULE_{hit['code']}" for hit in hits
        ]
        reasons += [code for code in risk_indicators(row) if code not in reasons]

        assessment = RiskAssessment(
            transaction_id=tx.id,
            model_version_id=model.id,
            risk_score=score,
            risk_level=level,
            reason_codes=reasons,
            rule_hits=hits,
        )
        db.add(assessment)
        assessments.append(assessment)

        should_alert = above or any(
            RiskLevel(hit["severity"]) in ALERTING_RULE_SEVERITIES for hit in hits
        )
        if should_alert and tx.id not in already_alerted:
            db.flush()  # need assessment.id
            alert = Alert(
                transaction_id=tx.id,
                risk_assessment_id=assessment.id,
                priority=level,
                status=AlertStatus.OPEN,
            )
            db.add(alert)
            alerts.append(alert)
            already_alerted.add(tx.id)
    db.flush()
    return assessments, alerts


# Arbitrary constant key for pg_advisory_xact_lock; held until the caller's transaction ends.
SCORING_LOCK_KEY = 7_311_004


def lock_scoring(db: Session) -> None:
    """Serialise scoring runs (CLI and API) so they cannot double-score or double-alert."""
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCORING_LOCK_KEY})


def unscored_transactions(db: Session, model: LoadedModel, limit: int) -> list[Transaction]:
    """Oldest transactions that have no assessment from the active model yet.

    Takes the scoring lock first, so two concurrent runs never pick the same rows.
    """
    lock_scoring(db)
    scored = exists().where(
        and_(
            RiskAssessment.transaction_id == Transaction.id,
            RiskAssessment.model_version_id == model.id,
        )
    )
    return list(
        db.scalars(
            select(Transaction)
            .where(~scored)
            .order_by(Transaction.occurred_at, Transaction.id)
            .limit(limit)
        )
    )
