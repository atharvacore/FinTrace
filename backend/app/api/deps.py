"""Shared FastAPI dependencies: database session, current user and role checks."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db import get_db
from app.models import User
from app.models.enums import ROLE_RANK, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(message: str) -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED,
        "UNAUTHORIZED",
        message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise _unauthorized("Authentication required")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid or expired token") from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User is inactive or no longer exists")
    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: Role) -> Callable[[User], User]:
    """Dependency factory: allow users whose role rank is >= `minimum`.

    Enforced on the server for every protected route, regardless of what the UI shows.
    """

    def _check(user: CurrentUser) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[minimum]:
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                f"This action requires the '{minimum.value}' role or higher",
            )
        return user

    return _check


AnalystUser = Annotated[User, Depends(require_role(Role.ANALYST))]
SeniorUser = Annotated[User, Depends(require_role(Role.SENIOR_ANALYST))]
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
