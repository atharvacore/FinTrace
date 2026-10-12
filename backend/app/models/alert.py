from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AlertStatus, RiskLevel
from app.models.scoring import RiskAssessment
from app.models.transaction import Transaction
from app.models.user import User


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # One alert per assessment: re-scoring creates a new assessment, never a duplicate alert.
    risk_assessment_id: Mapped[int] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    priority: Mapped[RiskLevel] = mapped_column(
        str_enum(RiskLevel, "alert_priority"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        str_enum(AlertStatus, "alert_status"), nullable=False, default=AlertStatus.OPEN
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    transaction: Mapped[Transaction] = relationship(lazy="joined")
    assessment: Mapped[RiskAssessment] = relationship(lazy="joined")
    assignee: Mapped[User | None] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_alerts_status_priority", "status", "priority"),
        Index("ix_alerts_created_at", "created_at"),
    )
