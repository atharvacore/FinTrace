"""Command-line helpers.

    python -m app.cli create-user --email admin@example.com --name "Admin" --role admin
    python -m app.cli import-csv ../data/sample/synthetic_transactions.csv [--limit 100000]
    python -m app.cli sync-model           # register + activate the artifact from training
    python -m app.cli score [--limit 5000] # score transactions the active model has not seen
    python -m app.cli demo-seed            # demo users + synthetic sample + model + scores + a case

The password is read from the FINTRACE_NEW_USER_PASSWORD environment variable if set,
otherwise prompted for (never passed as a command-line argument, so it stays out of shell history).
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import case, func, select

from app.core.config import REPO_ROOT, get_settings
from app.core.security import hash_password
from app.db import get_session_factory
from app.models import Alert, Case, CaseAlert, CaseNote, ModelVersion, User
from app.models.enums import AlertStatus, CaseStatus, RiskLevel, Role
from app.schemas.user import UserCreate
from app.services import cases as case_service
from app.services.audit import record_audit
from app.services.ingestion import import_csv
from app.services.model_registry import load_active, sync_from_promoted
from app.services.scoring import score_transactions, unscored_transactions


def create_user(email: str, name: str, role: Role, password: str) -> int:
    # Same validation as the API, so the CLI cannot create accounts the API would reject.
    try:
        data = UserCreate(email=email, full_name=name, role=role, password=password)
    except ValidationError as exc:
        messages = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise SystemExit(f"Invalid user details: {messages}") from None
    email = data.email
    with get_session_factory()() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email.lower())):
            raise SystemExit(f"User {email} already exists")
        user = User(
            email=email.lower(), full_name=name, role=role, password_hash=hash_password(password)
        )
        db.add(user)
        db.flush()
        record_audit(
            db,
            actor=None,
            action="user.created",
            entity_type="user",
            entity_id=user.id,
            after={"email": user.email, "role": role.value, "via": "cli"},
        )
        db.commit()
        return user.id


def import_file(path: Path, limit: int | None = None) -> None:
    """Import a CSV of any size (the API upload is capped; this streams from disk)."""
    with get_session_factory()() as db, path.open("rb") as fh:
        batch = import_csv(db, fh, path.name, uploaded_by=None, limit=limit)
        record_audit(
            db,
            actor=None,
            action="import.completed",
            entity_type="import_batch",
            entity_id=batch.id,
            after={"filename": batch.filename, "rows_inserted": batch.rows_inserted, "via": "cli"},
        )
        db.commit()
        print(
            f"Import {batch.id} ({batch.status.value}): {batch.rows_total} rows read, "
            f"{batch.rows_inserted} inserted, {batch.rows_duplicate} duplicates, "
            f"{batch.rows_rejected} rejected"
        )
        for err in batch.errors[:10]:
            print(f"  line {err['row']}: {'; '.join(err['errors'])}")


def sync_model() -> None:
    with get_session_factory()() as db:
        model, created = sync_from_promoted(db)
        record_audit(
            db,
            actor=None,
            action="model.registered" if created else "model.activated",
            entity_type="model_version",
            entity_id=model.id,
            after={"active_version": model.version, "via": "cli"},
        )
        db.commit()
        note = " (SYNTHETIC smoke-test model)" if model.is_synthetic_demo else ""
        print(f"{'Registered' if created else 'Re-activated'} model {model.version}{note}")


def score(limit: int) -> None:
    """Score in chunks of up to 5,000 until `limit` transactions are done or none are left."""
    done = alerts = 0
    with get_session_factory()() as db:
        model = load_active(db)
        while done < limit:
            batch = unscored_transactions(db, model, min(5000, limit - done))
            if not batch:
                break
            _, created = score_transactions(db, batch, model)
            db.commit()
            done += len(batch)
            alerts += len(created)
            print(f"  scored {done} so far, {alerts} alerts")
        record_audit(
            db,
            actor=None,
            action="scoring.run",
            entity_type="model_version",
            entity_id=model.id,
            after={"scored": done, "alerts_created": alerts, "via": "cli"},
        )
        db.commit()
    print(f"Scored {done} transactions with {model.version}; created {alerts} alerts")


SAMPLE_CSV = REPO_ROOT / "data" / "sample" / "synthetic_transactions.csv"
PRIORITY_RANK = case(
    {RiskLevel.CRITICAL: 4, RiskLevel.HIGH: 3, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 1},
    value=Alert.priority,
)
DEMO_USERS = [
    ("demo.analyst@example.com", "Ana Analyst", Role.ANALYST),
    ("demo.senior@example.com", "Sam Senior", Role.SENIOR_ANALYST),
    ("demo.admin@example.com", "Ada Admin", Role.ADMIN),
]


def _ensure_model() -> None:
    """Use the active model; else register the promoted artifact; else train a demo model."""
    settings = get_settings()
    with get_session_factory()() as db:
        if db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True))):
            print("Model: using the active model")
            return
    if not (settings.model_dir / "model.joblib").is_file():
        from fintrace_ml.train import promote, run

        print(
            "Model: none found, training a SYNTHETIC smoke-test model on the bundled sample "
            "(its scores are not results; train on PaySim for a real model)"
        )
        out = run(SAMPLE_CSV, "synthetic", REPO_ROOT / "ml" / "artifacts", seed=42)
        promote(out, settings.model_dir)
    sync_model()


def _demo_case(analyst_email: str) -> None:
    """Open one example case from the two highest-priority alerts, if there are no cases yet."""
    with get_session_factory()() as db:
        if db.scalar(select(func.count()).select_from(Case)):
            return
        analyst = db.scalar(select(User).where(User.email == analyst_email))
        unlinked = ~select(CaseAlert.alert_id).where(CaseAlert.alert_id == Alert.id).exists()
        alerts = list(
            db.scalars(
                select(Alert)
                .where(Alert.status == AlertStatus.OPEN, unlinked)
                .order_by(PRIORITY_RANK.desc(), Alert.id)
                .limit(2)
            ).unique()
        )
        if analyst is None or not alerts:
            return
        case_id, reference = case_service.next_reference(db)
        case = Case(
            id=case_id,
            reference=reference,
            title="Demo: transfers that empty the sending account",
            description="Example case created by demo-seed from the highest-priority alerts.",
            priority=alerts[0].priority,
            status=CaseStatus.INVESTIGATING,
            assignee_id=analyst.id,
            created_by_id=analyst.id,
        )
        db.add(case)
        db.flush()
        linked = case_service.link_alerts(db, case, [a.id for a in alerts], analyst)
        db.add(
            CaseNote(
                case_id=case.id,
                author_id=analyst.id,
                body="Both transfers take the full origin balance. Checking where the funds went.",
            )
        )
        record_audit(
            db,
            actor=analyst,
            action="case.created",
            entity_type="case",
            entity_id=case.id,
            after={**case_service.snapshot(case), "reference": reference, "alert_ids": linked},
        )
        db.commit()
        print(f"Case: opened {reference} with alerts {linked}")


def demo_seed(password: str, csv_path: Path) -> None:
    """Idempotent demo setup: safe to run again, it only adds what is missing."""
    for email, name, role in DEMO_USERS:
        with get_session_factory()() as db:
            exists = db.scalar(select(User).where(User.email == email))
        if exists:
            print(f"User: {email} already exists")
        else:
            create_user(email, name, role, password)
            print(f"User: created {email} ({role.value})")
    import_file(csv_path)
    _ensure_model()
    score(limit=1_000_000)
    _demo_case(DEMO_USERS[0][0])
    print("Demo ready. Sign in as demo.analyst@example.com or demo.senior@example.com.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user", help="Create a user account")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", required=True, choices=[r.value for r in Role])
    ic = sub.add_parser("import-csv", help="Import a PaySim-format CSV file")
    ic.add_argument("path", type=Path)
    ic.add_argument("--limit", type=int, default=None, help="Stop after this many rows")
    sub.add_parser("sync-model", help="Register and activate the promoted model artifact")
    sc = sub.add_parser("score", help="Score transactions not yet scored by the active model")
    sc.add_argument("--limit", type=int, default=100_000)
    ds = sub.add_parser(
        "demo-seed",
        help="Create demo users (password from FINTRACE_DEMO_PASSWORD), import the synthetic "
        "sample, register or train a model, score, and open an example case",
    )
    ds.add_argument("--csv", type=Path, default=SAMPLE_CSV)
    args = parser.parse_args(argv)

    if args.command == "create-user":
        password = os.environ.get("FINTRACE_NEW_USER_PASSWORD") or getpass.getpass("Password: ")
        user_id = create_user(args.email, args.name, Role(args.role), password)
        print(f"Created user {args.email} (id={user_id}, role={args.role})")
    elif args.command == "import-csv":
        if not args.path.is_file():
            raise SystemExit(f"File not found: {args.path}")
        import_file(args.path, args.limit)
    elif args.command == "sync-model":
        sync_model()
    elif args.command == "score":
        score(args.limit)
    elif args.command == "demo-seed":
        password = os.environ.get("FINTRACE_DEMO_PASSWORD", "")
        if len(password) < 12:
            raise SystemExit("Set FINTRACE_DEMO_PASSWORD (at least 12 characters) first.")
        if not args.csv.is_file():
            raise SystemExit(f"File not found: {args.csv}")
        demo_seed(password, args.csv)


if __name__ == "__main__":
    main(sys.argv[1:])
