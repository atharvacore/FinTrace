from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CaseDecision, CaseStatus, RiskLevel, Role
from app.schemas.common import ORMModel
from app.schemas.scoring import AlertRead, UserSummary


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10_000)
    priority: RiskLevel = RiskLevel.MEDIUM
    assignee_id: int | None = Field(
        default=None, description="Defaults to you. Analysts may only assign themselves."
    )
    alert_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("title must have at least 3 non-blank characters")
        return value


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: CaseStatus | None = Field(
        default=None, description="open, investigating or pending_decision. Close with a decision."
    )
    priority: RiskLevel | None = None
    assignee_id: int | None = Field(default=None, description="Send null to unassign")


class CaseLinkAlerts(BaseModel):
    alert_ids: list[int] = Field(min_length=1, max_length=100)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("note must not be blank")
        return value.strip()


class DecisionCreate(BaseModel):
    decision: CaseDecision
    rationale: str = Field(min_length=10, max_length=10_000)

    @field_validator("rationale")
    @classmethod
    def _meaningful(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("rationale must explain the decision (at least 10 characters)")
        return value


class CaseRead(ORMModel):
    id: int
    reference: str
    title: str
    status: CaseStatus
    priority: RiskLevel
    assignee: UserSummary | None
    created_by: UserSummary
    decision: CaseDecision | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    alert_count: int
    note_count: int


class NoteRead(ORMModel):
    id: int
    body: str
    author: UserSummary
    created_at: datetime


class AuditEventRead(ORMModel):
    id: int
    actor: UserSummary | None
    action: str
    entity_type: str
    entity_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    request_id: str | None
    created_at: datetime


class CaseDetail(CaseRead):
    description: str
    decision_rationale: str | None
    decided_by: UserSummary | None
    alerts: list[AlertRead]
    notes: list[NoteRead]
    timeline: list[AuditEventRead] = Field(description="Audit events for this case, oldest first")


class AssignableUser(ORMModel):
    id: int
    full_name: str
    role: Role
