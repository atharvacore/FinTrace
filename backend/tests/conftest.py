"""Test fixtures. Tests run against a real PostgreSQL database (never SQLite).

Set FINTRACE_TEST_DATABASE_URL to point at an empty, disposable database.
"""

import importlib.util
import os
import secrets
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

TEST_DB_URL = os.environ.get(
    "FINTRACE_TEST_DATABASE_URL",
    "postgresql+psycopg://fintrace:fintrace@localhost:5432/fintrace_test",
)
# Configure the app before it is imported anywhere.
os.environ["FINTRACE_ENV"] = "test"
os.environ["FINTRACE_DATABASE_URL"] = TEST_DB_URL
os.environ["FINTRACE_JWT_SECRET"] = secrets.token_urlsafe(48)
os.environ["FINTRACE_MODEL_DIR"] = str(Path(__file__).parent / "_no_model_here")
os.environ["FINTRACE_MODEL_REGISTRY_DIR"] = tempfile.mkdtemp(prefix="fintrace-registry-")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import get_engine, get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, MonitoringRule, User  # noqa: E402
from app.models.enums import Role  # noqa: E402

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV = REPO_ROOT / "data" / "sample" / "synthetic_transactions.csv"


def _default_rules() -> list[dict]:
    """The rules seeded by migration 0002, read from the migration itself."""
    path = next((ALEMBIC_INI.parent / "alembic" / "versions").glob("0002_*.py"))
    spec = importlib.util.spec_from_file_location("migration_0002", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DEFAULT_RULES


TEST_PASSWORD = "correct-horse-battery-staple"


def alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    """Build the schema with the real migrations, exactly as a fresh install would."""
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # noqa: S608
        # Restore the seeded monitoring rules, as a fresh migration would leave them.
        conn.execute(MonitoringRule.__table__.insert(), _default_rules())


@pytest.fixture
def db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(
        role: Role = Role.ANALYST,
        email: str | None = None,
        password: str = TEST_PASSWORD,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email or f"{role.value}-{secrets.token_hex(3)}@example.com",
            full_name=f"Test {role.value}",
            role=role,
            password_hash=hash_password(password),
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def login(client: TestClient) -> Callable[[User], dict[str, str]]:
    def _login(user: User, password: str = TEST_PASSWORD) -> dict[str, str]:
        resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _login


# ---------------------------------------------------------------- model fixtures


@pytest.fixture(scope="session")
def synthetic_artifact(tmp_path_factory) -> Path:
    """A real model trained on the bundled SYNTHETIC sample (smoke-test quality only)."""
    from fintrace_ml.train import run

    return run(SAMPLE_CSV, "synthetic", tmp_path_factory.mktemp("artifacts"), seed=3)


@pytest.fixture
def promoted(synthetic_artifact, monkeypatch, tmp_path) -> Path:
    """Point FINTRACE_MODEL_DIR at a promoted copy of the synthetic artifact."""
    import shutil

    from app.core.config import get_settings

    current = tmp_path / "current"
    shutil.copytree(synthetic_artifact, current)
    monkeypatch.setattr(get_settings(), "model_dir", current)
    return current


@pytest.fixture
def active_model(promoted, db):
    from app.services.model_registry import sync_from_promoted

    model, _ = sync_from_promoted(db)
    db.commit()
    return model


@pytest.fixture
def imported_sample(db):
    from app.services.ingestion import import_csv

    with SAMPLE_CSV.open("rb") as fh:
        batch = import_csv(db, fh, SAMPLE_CSV.name, uploaded_by=None)
    db.commit()
    return batch


@pytest.fixture
def scored(client, make_user, login, imported_sample, active_model):
    senior = login(make_user(Role.SENIOR_ANALYST))
    resp = client.post("/api/v1/scoring/run", json={"limit": 5000}, headers=senior).json()
    assert resp["alerts_created"] >= 3
    return resp


@pytest.fixture
def people(make_user, login):
    analyst = make_user(Role.ANALYST)
    other = make_user(Role.ANALYST)
    senior = make_user(Role.SENIOR_ANALYST)
    return {
        "analyst": (analyst, login(analyst)),
        "other": (other, login(other)),
        "senior": (senior, login(senior)),
    }
