from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Role
from app.schemas.common import ORMModel

PASSWORD_MIN_LENGTH = 12


class UserRead(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=256)

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=PASSWORD_MIN_LENGTH, max_length=256)
