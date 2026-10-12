from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import CaseDecision, CaseStatus, RiskLevel
from app.models.user import User


class Case(TimestampMixin, Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[CaseStatus] = mapped_column(
        str_enum(CaseStatus, "case_status"), nullable=False, default=CaseStatus.OPEN
    )
    priority: Mapped[RiskLevel] = mapped_column(
        str_enum(RiskLevel, "case_priority"), nullable=False
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[CaseDecision | None] = mapped_column(str_enum(CaseDecision, "case_decision"))
    decision_rationale: Mapped[str | None] = mapped_column(Text)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id], lazy="joined")
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_id], lazy="joined")

    __table_args__ = (
        # A closed case must carry a decision; an open case must not.
        CheckConstraint("(status = 'closed') = (decision IS NOT NULL)", name="closed_iff_decided"),
        CheckConstraint(
            "decision IS NULL OR (decision_rationale IS NOT NULL AND decided_by_id IS NOT NULL "
            "AND decided_at IS NOT NULL)",
            name="decision_complete",
        ),
        Index("ix_cases_status", "status"),
    )


class CaseAlert(Base):
    __tablename__ = "case_alerts"

    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), primary_key=True
    )
    # Unique: an alert belongs to at most one case.
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="RESTRICT"), primary_key=True, unique=True
    )
    linked_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CaseNote(Base):
    """Append-only investigation notes."""

    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[User] = relationship(lazy="joined")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (CheckConstraint("length(trim(body)) > 0", name="body_not_blank"),)
