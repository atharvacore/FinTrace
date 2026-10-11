"""Test fixtures. Tests run against a real PostgreSQL database (never SQLite).

Set FINTRACE_TEST_DATABASE_URL to point at an empty, disposable database.
"""

import os
import secrets
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

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import get_engine, get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.models.enums import Role  # noqa: E402

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
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
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


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
