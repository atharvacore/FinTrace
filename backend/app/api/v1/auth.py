from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import ErrorResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID = AppError(
    status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Invalid email or password"
)


def _authenticate(db: DbSession, email: str, password: str) -> TokenResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if not verify_password(password, user.password_hash if user else None) or user is None:
        raise _INVALID
    if not user.is_active:
        raise _INVALID  # same message: do not reveal that the account exists
    user.last_login_at = datetime.now(UTC)
    db.commit()
    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with email and password (JSON)",
    responses={401: {"model": ErrorResponse}},
)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    return _authenticate(db, body.email, body.password)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="OAuth2 password flow (used by the Swagger UI 'Authorize' button)",
    responses={401: {"model": ErrorResponse}},
)
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> TokenResponse:
    return _authenticate(db, form.username, form.password)


@router.get("/me", response_model=UserRead, summary="Current user")
def me(user: CurrentUser) -> User:
    return user
