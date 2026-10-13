from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

SYNTHETIC_NOTICE = (
    "Synthetic data. Labels are simulated fraud, not confirmed money laundering. Scores are "
    "triage signals for human review, not proof of wrongdoing."
)


class ActiveModelSummary(BaseModel):
    id: int
    version: str
    threshold: Decimal
    is_synthetic_demo: bool


class LabelCheck(BaseModel):
    """How alerts line up with the dataset's synthetic labels. Evaluation only."""

    scored_with_label: int
    labelled_fraud_scored: int
    labelled_fraud_alerted: int
    alerts_with_label: int
    alerts_labelled_fraud: int
    note: str = (
        "Computed from the synthetic dataset's own labels. Real investigations have no such "
        "ground truth; analysts' decisions are the outcome that matters."
    )


class Overview(BaseModel):
    notice: str = SYNTHETIC_NOTICE
    transactions_total: int
    transactions_scored: int = Field(description="Scored by the active model")
    transactions_unscored: int
    alerts_total: int
    alerts_by_status: dict[str, int]
    open_alerts_by_priority: dict[str, int]
    alerts_per_1000_scored: float | None
    cases_by_status: dict[str, int]
    decisions: dict[str, int]
    my_open_alerts: int
    my_open_cases: int
    active_model: ActiveModelSummary | None
    label_check: LabelCheck | None


class RiskBin(BaseModel):
    lower: float
    upper: float
    count: int
    labelled_fraud: int


class RiskDistribution(BaseModel):
    notice: str = SYNTHETIC_NOTICE
    model_version: str
    threshold: Decimal
    transactions: int
    bins: list[RiskBin]
    by_level: dict[str, int]
    above_threshold: int


class ModelEvaluation(BaseModel):
    notice: str = SYNTHETIC_NOTICE
    version: str
    algorithm: str
    feature_set: str
    threshold: Decimal
    is_synthetic_demo: bool
    trained_at: datetime
    data_kind: str | None
    dataset: dict[str, Any]
    split: dict[str, Any]
    selection: dict[str, Any]
    methodology: list[str]
    models: dict[str, Any] = Field(description="Validation and test metrics per candidate model")
    caveats: list[str]
