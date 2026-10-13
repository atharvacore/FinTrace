"""demo-seed sets up a working demo and is safe to run twice."""

import pytest
from sqlalchemy import func, select

from app.models import Alert, Case, ModelVersion, Transaction, User


@pytest.mark.usefixtures("promoted")
def test_demo_seed_is_idempotent(db, capsys):
    from app.cli import SAMPLE_CSV, demo_seed

    demo_seed("demo-password-12345", SAMPLE_CSV)
    count = lambda model: db.scalar(select(func.count()).select_from(model))  # noqa: E731
    first = {m: count(m) for m in (User, Transaction, ModelVersion, Alert, Case)}
    assert first[User] == 3 and first[Transaction] == 5000 and first[ModelVersion] == 1
    assert first[Alert] > 0 and first[Case] == 1
    case = db.scalar(select(Case))
    assert case.assignee.email == "demo.analyst@example.com"

    demo_seed("demo-password-12345", SAMPLE_CSV)
    db.expire_all()
    assert {m: count(m) for m in first} == first
    assert "already exists" in capsys.readouterr().out


def test_demo_seed_requires_a_password(monkeypatch):
    from app.cli import main

    monkeypatch.delenv("FINTRACE_DEMO_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="FINTRACE_DEMO_PASSWORD"):
        main(["demo-seed"])
