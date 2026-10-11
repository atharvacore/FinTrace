from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum
from app.models.enums import RiskLevel


class MonitoringRule(Base):
    __tablename__ = "monitoring_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    severity: Mapped[RiskLevel] = mapped_column(
        str_enum(RiskLevel, "rule_severity"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_set: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("threshold > 0 AND threshold < 1", name="threshold_range"),
        # At most one active model at a time.
        Index(
            "uq_model_versions_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )
    # NULL means the assessment came from rules only (no model was available).
    model_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"), index=True
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(str_enum(RiskLevel, "risk_level"), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    rule_hits: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="risk_score_range"),
        Index("ix_risk_assessments_transaction_scored", "transaction_id", text("scored_at DESC")),
        Index("ix_risk_assessments_risk_level", "risk_level"),
    )
