"""Import every model so Base.metadata is complete (used by Alembic autogenerate)."""

from app.models.alert import Alert
from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.case import Case, CaseAlert, CaseNote
from app.models.scoring import ModelVersion, MonitoringRule, RiskAssessment
from app.models.transaction import ImportBatch, Transaction
from app.models.user import User

__all__ = [
    "Alert",
    "AuditEvent",
    "Base",
    "Case",
    "CaseAlert",
    "CaseNote",
    "ImportBatch",
    "ModelVersion",
    "MonitoringRule",
    "RiskAssessment",
    "Transaction",
    "User",
]
