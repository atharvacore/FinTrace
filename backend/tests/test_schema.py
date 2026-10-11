"""Migration round-trip and database-level constraints (the DB enforces rules, not just the API)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import get_engine
from app.models import Case, ModelVersion, Transaction
from app.models.enums import CaseStatus, RiskLevel, Role, TransactionSource, TransactionType
from tests.conftest import alembic_config


def test_migrations_downgrade_and_upgrade_cleanly():
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    assert set(inspect(get_engine()).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    tables = set(inspect(get_engine()).get_table_names())
    assert {"users", "transactions", "alerts", "cases", "audit_events"} <= tables


def _transaction(**overrides) -> Transaction:
    values = dict(
        dedup_key="k" * 64,
        source=TransactionSource.API,
        step=1,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        origin_account="C1",
        dest_account="C2",
        origin_balance_before=Decimal("100"),
        origin_balance_after=Decimal("0"),
        dest_balance_before=Decimal("0"),
        dest_balance_after=Decimal("100"),
    )
    return Transaction(**(values | overrides))


def test_non_positive_amount_rejected_by_database(db):
    db.add(_transaction(amount=Decimal("0")))
    with pytest.raises(IntegrityError, match="ck_transactions_amount_positive"):
        db.commit()


def test_duplicate_dedup_key_rejected_by_database(db):
    db.add(_transaction())
    db.commit()
    db.add(_transaction())
    with pytest.raises(IntegrityError, match="uq_transactions_dedup_key"):
        db.commit()


def test_closed_case_requires_decision(db, make_user):
    user = make_user(Role.SENIOR_ANALYST)
    db.add(
        Case(
            reference="CASE-000001",
            title="t",
            status=CaseStatus.CLOSED,
            priority=RiskLevel.HIGH,
            created_by_id=user.id,
        )
    )
    with pytest.raises(IntegrityError, match="ck_cases_closed_iff_decided"):
        db.commit()


def test_only_one_active_model_version(db):
    def model(version: str) -> ModelVersion:
        return ModelVersion(
            version=version,
            algorithm="x",
            artifact_path="p",
            artifact_sha256="s" * 64,
            feature_set="strict",
            threshold=Decimal("0.5"),
            dataset_fingerprint="d" * 64,
            trained_at=datetime.now(UTC),
            is_active=True,
        )

    db.add(model("v1"))
    db.commit()
    db.add(model("v2"))
    with pytest.raises(IntegrityError, match="uq_model_versions_single_active"):
        db.commit()
