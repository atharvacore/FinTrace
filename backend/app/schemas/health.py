from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ComponentStatus(BaseModel):
    status: Literal["ok", "unavailable", "outdated", "missing"]
    detail: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: ComponentStatus
    migrations: ComponentStatus
    model: ComponentStatus
