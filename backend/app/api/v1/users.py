from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession
from app.core.errors import AppError, conflict, not_found
from app.core.security import hash_password
from app.models import User
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit import record_audit

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


def _snapshot(user: User) -> dict:
    # Never include the password hash in audit records.
    return {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }


@router.get("", response_model=Page[UserRead], summary="List users")
def list_users(
    _: AdminUser, db: DbSession, params: Annotated[PageParams, Depends()]
) -> Page[UserRead]:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    users = db.scalars(
        select(User).order_by(User.id).offset(params.offset).limit(params.page_size)
    ).all()
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    responses={409: {"model": ErrorResponse}},
)
def create_user(body: UserCreate, admin: AdminUser, db: DbSession, request: Request) -> User:
    user = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict("EMAIL_TAKEN", f"A user with email {body.email} already exists") from None
    record_audit(
        db,
        actor=admin,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        after=_snapshot(user),
        request=request,
    )
    db.commit()
    return user


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user's name, role, active flag or password",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_user(
    user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession, request: Request
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        ("role" in changes and changes["role"] != user.role) or changes.get("is_active") is False
    ):
        # Prevents an admin locking everyone out by demoting or deactivating themselves.
        raise AppError(
            status.HTTP_409_CONFLICT,
            "SELF_LOCKOUT",
            "Admins cannot change their own role or deactivate themselves",
        )

    before = _snapshot(user)
    for field in ("full_name", "role", "is_active"):
        if field in changes and changes[field] is not None:
            setattr(user, field, changes[field])
    if changes.get("password"):
        user.password_hash = hash_password(changes["password"])

    after = _snapshot(user)
    if changes.get("password"):
        after["password_changed"] = True
    record_audit(
        db,
        actor=admin,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=after,
        request=request,
    )
    db.commit()
    return user
