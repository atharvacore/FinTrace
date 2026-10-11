"""Password hashing (Argon2) and JWT access tokens."""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()  # Argon2id with library-recommended parameters

# Verified against when the email is unknown, so response time does not reveal which emails exist.
_DUMMY_HASH = _password_hash.hash("timing-equaliser-not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    settings = get_settings()
    expires_in = settings.access_token_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "typ": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """Decode and validate a token; raises jwt.PyJWTError if invalid or expired."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "iat"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
