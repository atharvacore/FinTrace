"""Domain enumerations shared by models, schemas and services."""

from enum import StrEnum


class Role(StrEnum):
    ANALYST = "analyst"
    SENIOR_ANALYST = "senior_analyst"
    ADMIN = "admin"


# Higher rank includes the permissions of lower ranks.
ROLE_RANK = {Role.ANALYST: 1, Role.SENIOR_ANALYST: 2, Role.ADMIN: 3}


class TransactionType(StrEnum):
    """The five PaySim transaction types."""

    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"
    DEBIT = "DEBIT"
    PAYMENT = "PAYMENT"
    TRANSFER = "TRANSFER"


class TransactionSource(StrEnum):
    CSV = "csv"
    API = "api"


class ImportStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    CLOSED_FALSE_POSITIVE = "closed_false_positive"
    CLOSED_ACTIONED = "closed_actioned"


class CaseStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    PENDING_DECISION = "pending_decision"
    CLOSED = "closed"


class CaseDecision(StrEnum):
    NO_FURTHER_ACTION = "no_further_action"
    FALSE_POSITIVE = "false_positive"
    ESCALATE_FOR_REPORTING = "escalate_for_reporting"
