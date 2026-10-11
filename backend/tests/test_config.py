import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("secret", ["", "CHANGE_ME", "too-short"])
def test_app_refuses_missing_or_placeholder_jwt_secret(secret):
    with pytest.raises(ValidationError, match="FINTRACE_JWT_SECRET"):
        Settings(jwt_secret=secret, _env_file=None)


def test_cors_origins_accept_comma_separated_string():
    settings = Settings(
        jwt_secret="x" * 40, cors_origins="http://a.test, http://b.test", _env_file=None
    )
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_from_environment_variable(monkeypatch):
    monkeypatch.setenv("FINTRACE_CORS_ORIGINS", "http://a.test,http://b.test")
    settings = Settings(jwt_secret="x" * 40, _env_file=None)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
