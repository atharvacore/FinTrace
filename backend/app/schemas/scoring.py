from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AlertStatus, RiskLevel
from app.schemas.common import ORMModel
from app.schemas.transaction import AlertSummary, TransactionDetail, TransactionRead


class RuleHit(BaseModel):
    code: str
    name: str
    severity: RiskLevel
    detail: str


class RiskAssessmentRead(ORMModel):
    id: int
    transaction_id: int
    model_version_id: int
    model_version: str
    risk_score: Decimal
    risk_level: RiskLevel
    reason_codes: list[str]
    rule_hits: list[RuleHit]
    scored_at: datetime


class ScoreRunRequest(BaseModel):
    limit: int = Field(default=1000, ge=1, le=5000)


class ScoreRunResult(BaseModel):
    model_version: str
    scored: int
    alerts_created: int
    remaining_unscored: int


class ScoreOneResult(BaseModel):
    assessment: RiskAssessmentRead
    alert_id: int | None


class ModelVersionRead(ORMModel):
    id: int
    version: str
    algorithm: str
    feature_set: str
    threshold: Decimal
    is_active: bool
    is_synthetic_demo: bool
    trained_at: datetime
    registered_at: datetime
    dataset_fingerprint: str
    artifact_sha256: str


class ModelVersionDetail(ModelVersionRead):
    metrics: dict[str, Any] = Field(description="Full training metadata and evaluation results")


class RuleRead(ORMModel):
    id: int
    code: str
    name: str
    description: str
    rule_type: str
    parameters: dict[str, Any]
    severity: RiskLevel
    enabled: bool
    updated_by_id: int | None
    updated_at: datetime


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    parameters: dict[str, Any] | None = None
    severity: RiskLevel | None = None
    enabled: bool | None = None


class UserSummary(ORMModel):
    id: int
    full_name: str
    email: str


class AlertRead(ORMModel):
    id: int
    status: AlertStatus
    priority: RiskLevel
    assignee: UserSummary | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    transaction: TransactionRead
    risk_score: Decimal
    reason_codes: list[str]
    model_version: str
    case_id: int | None = None


class AlertDetail(AlertRead):
    assessment: RiskAssessmentRead


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    assignee_id: int | None = Field(
        default=None, description="User to assign; send null to unassign"
    )


class TransactionWithHistory(TransactionDetail):
    assessments: list[RiskAssessmentRead]
    alerts: list[AlertSummary]
