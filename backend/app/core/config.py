"""Application settings loaded from environment variables (and an optional .env file).

Every setting uses the FINTRACE_ prefix, e.g. FINTRACE_DATABASE_URL.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: backend/app/core/config.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]

# Placeholder values from .env.example that must never be used for real.
_UNSAFE_SECRETS = {"", "CHANGE_ME", "changeme", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FINTRACE_",
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://fintrace:fintrace@localhost:5432/fintrace"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(default=60, ge=5, le=24 * 60)
    cors_origins: list[str] = ["http://localhost:5173"]
    model_dir: Path = REPO_ROOT / "ml" / "artifacts" / "current"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("model_dir", mode="after")
    @classmethod
    def _resolve_model_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else REPO_ROOT / value

    @model_validator(mode="after")
    def _require_real_secret(self) -> "Settings":
        # Refuse to start with a missing or placeholder JWT secret. Tests set their own.
        if self.jwt_secret in _UNSAFE_SECRETS or len(self.jwt_secret) < 32:
            raise ValueError(
                "FINTRACE_JWT_SECRET must be set to at least 32 random characters. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
