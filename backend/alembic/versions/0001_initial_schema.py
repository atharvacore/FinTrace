"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-11 06:55:11.418520
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("artifact_path", sa.String(length=500), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("feature_set", sa.String(length=64), nullable=False),
        sa.Column("threshold", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "threshold > 0 AND threshold < 1", name=op.f("ck_model_versions_threshold_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_model_versions_version")),
    )
    op.create_index(
        "uq_model_versions_single_active",
        "model_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "analyst",
                "senior_analyst",
                "admin",
                name="role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"], unique=False
    )
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "investigating",
                "pending_decision",
                "closed",
                name="case_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="case_priority",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(
                "no_further_action",
                "false_positive",
                "escalate_for_reporting",
                name="case_decision",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'closed') = (decision IS NOT NULL)", name=op.f("ck_cases_closed_iff_decided")
        ),
        sa.CheckConstraint(
            "decision IS NULL OR (decision_rationale IS NOT NULL AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL)",
            name=op.f("ck_cases_decision_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_cases_assignee_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_cases_created_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_cases_decided_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
        sa.UniqueConstraint("reference", name=op.f("uq_cases_reference")),
    )
    op.create_index(op.f("ix_cases_assignee_id"), "cases", ["assignee_id"], unique=False)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "completed",
                "completed_with_errors",
                "failed",
                name="import_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rows_total >= 0 AND rows_inserted >= 0 AND rows_duplicate >= 0 AND rows_rejected >= 0",
            name=op.f("ck_import_batches_row_counts_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_import_batches_uploaded_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
    )
    op.create_index(
        op.f("ix_import_batches_created_at"), "import_batches", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_import_batches_file_sha256"), "import_batches", ["file_sha256"], unique=False
    )
    op.create_index(
        op.f("ix_import_batches_uploaded_by_id"), "import_batches", ["uploaded_by_id"], unique=False
    )
    op.create_table(
        "monitoring_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="rule_severity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_monitoring_rules_updated_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitoring_rules")),
        sa.UniqueConstraint("code", name=op.f("uq_monitoring_rules_code")),
    )
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(body)) > 0", name=op.f("ck_case_notes_body_not_blank")),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_case_notes_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_case_notes_case_id_cases"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_notes")),
    )
    op.create_index(op.f("ix_case_notes_case_id"), "case_notes", ["case_id"], unique=False)
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dedup_key", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "csv",
                "api",
                name="transaction_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "CASH_IN",
                "CASH_OUT",
                "DEBIT",
                "PAYMENT",
                "TRANSFER",
                name="transaction_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("origin_account", sa.String(length=64), nullable=False),
        sa.Column("dest_account", sa.String(length=64), nullable=False),
        sa.Column("origin_balance_before", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("origin_balance_after", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("dest_balance_before", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("dest_balance_after", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("label_is_fraud", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_transactions_amount_positive")),
        sa.CheckConstraint(
            "origin_balance_before >= 0 AND origin_balance_after >= 0 AND dest_balance_before >= 0 AND dest_balance_after >= 0",
            name=op.f("ck_transactions_balances_non_negative"),
        ),
        sa.CheckConstraint("step >= 0", name=op.f("ck_transactions_step_non_negative")),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            name=op.f("fk_transactions_import_batch_id_import_batches"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_transactions_dedup_key")),
    )
    op.create_index(
        op.f("ix_transactions_dest_account"), "transactions", ["dest_account"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_import_batch_id"), "transactions", ["import_batch_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_occurred_at"), "transactions", ["occurred_at"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_origin_account"), "transactions", ["origin_account"], unique=False
    )
    op.create_index(op.f("ix_transactions_type"), "transactions", ["type"], unique=False)
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=True),
        sa.Column("risk_score", sa.Numeric(precision=6, scale=5), nullable=False),
        sa.Column(
            "risk_level",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="risk_level",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("reason_codes", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("rule_hits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "scored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 1", name=op.f("ck_risk_assessments_risk_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name=op.f("fk_risk_assessments_model_version_id_model_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_risk_assessments_transaction_id_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_assessments")),
    )
    op.create_index(
        op.f("ix_risk_assessments_model_version_id"),
        "risk_assessments",
        ["model_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_assessments_risk_level", "risk_assessments", ["risk_level"], unique=False
    )
    op.create_index(
        "ix_risk_assessments_transaction_scored",
        "risk_assessments",
        ["transaction_id", sa.literal_column("scored_at DESC")],
        unique=False,
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("risk_assessment_id", sa.Integer(), nullable=False),
        sa.Column(
            "priority",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="alert_priority",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "in_review",
                "escalated",
                "closed_false_positive",
                "closed_actioned",
                name="alert_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_alerts_assignee_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["risk_assessment_id"],
            ["risk_assessments.id"],
            name=op.f("fk_alerts_risk_assessment_id_risk_assessments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_alerts_transaction_id_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
        sa.UniqueConstraint("risk_assessment_id", name=op.f("uq_alerts_risk_assessment_id")),
    )
    op.create_index(op.f("ix_alerts_assignee_id"), "alerts", ["assignee_id"], unique=False)
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"], unique=False)
    op.create_index("ix_alerts_status_priority", "alerts", ["status", "priority"], unique=False)
    op.create_index(op.f("ix_alerts_transaction_id"), "alerts", ["transaction_id"], unique=False)
    op.create_table(
        "case_alerts",
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("linked_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_case_alerts_alert_id_alerts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_case_alerts_case_id_cases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["linked_by_id"],
            ["users.id"],
            name=op.f("fk_case_alerts_linked_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("case_id", "alert_id", name=op.f("pk_case_alerts")),
        sa.UniqueConstraint("alert_id", name=op.f("uq_case_alerts_alert_id")),
    )


def downgrade() -> None:
    op.drop_table("case_alerts")
    op.drop_index(op.f("ix_alerts_transaction_id"), table_name="alerts")
    op.drop_index("ix_alerts_status_priority", table_name="alerts")
    op.drop_index("ix_alerts_created_at", table_name="alerts")
    op.drop_index(op.f("ix_alerts_assignee_id"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_risk_assessments_transaction_scored", table_name="risk_assessments")
    op.drop_index("ix_risk_assessments_risk_level", table_name="risk_assessments")
    op.drop_index(op.f("ix_risk_assessments_model_version_id"), table_name="risk_assessments")
    op.drop_table("risk_assessments")
    op.drop_index(op.f("ix_transactions_type"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_origin_account"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_occurred_at"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_import_batch_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_dest_account"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_case_notes_case_id"), table_name="case_notes")
    op.drop_table("case_notes")
    op.drop_table("monitoring_rules")
    op.drop_index(op.f("ix_import_batches_uploaded_by_id"), table_name="import_batches")
    op.drop_index(op.f("ix_import_batches_file_sha256"), table_name="import_batches")
    op.drop_index(op.f("ix_import_batches_created_at"), table_name="import_batches")
    op.drop_table("import_batches")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index(op.f("ix_cases_assignee_id"), table_name="cases")
    op.drop_table("cases")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_index(
        "uq_model_versions_single_active",
        table_name="model_versions",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_table("model_versions")
