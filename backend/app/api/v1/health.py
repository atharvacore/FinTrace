from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.core.config import get_settings
from app.db import get_engine
from app.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


@router.get("", response_model=HealthResponse, summary="Liveness check")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness: database, migrations and model artifact",
    responses={503: {"model": ReadinessResponse}},
)
def ready(response: Response) -> ReadinessResponse:
    database = ComponentStatus(status="ok", detail="Connected")
    migrations = ComponentStatus(status="ok", detail="")
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            current = MigrationContext.configure(conn).get_current_revision()
        head = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()
        if current == head:
            migrations = ComponentStatus(status="ok", detail=f"At head revision {head}")
        else:
            migrations = ComponentStatus(
                status="outdated",
                detail=f"Database at {current}, code expects {head}. Run: alembic upgrade head",
            )
    except SQLAlchemyError as exc:
        database = ComponentStatus(status="unavailable", detail=type(exc).__name__)
        migrations = ComponentStatus(status="unavailable", detail="Database unreachable")

    # The model is optional for readiness: without it, only rules-based scoring is available.
    metadata_file = get_settings().model_dir / "metadata.json"
    if metadata_file.is_file():
        model = ComponentStatus(status="ok", detail=f"Artifact found at {metadata_file.parent}")
    else:
        model = ComponentStatus(
            status="missing",
            detail="No model artifact. Train one with the ml pipeline "
            "(see README, 'Train the model').",
        )

    is_ready = database.status == "ok" and migrations.status == "ok"
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        database=database,
        migrations=migrations,
        model=model,
    )
