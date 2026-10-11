from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import AnalystUser, DbSession, SeniorUser
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.models import ImportBatch
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.transaction import ImportBatchRead
from app.services.audit import record_audit
from app.services.ingestion import import_csv

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)


@router.post(
    "",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PaySim-format CSV",
    description=(
        "Validates every row. Valid rows are inserted, invalid rows are reported with their "
        "line number, and rows already in the database are counted as duplicates. "
        "Uploading the same file twice inserts nothing the second time."
    ),
    responses={413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def upload_csv(
    request: Request,
    user: SeniorUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="CSV with the PaySim header")],
) -> ImportBatch:
    max_mb = get_settings().max_upload_mb
    if file.size is not None and file.size > max_mb * 1024 * 1024:
        raise AppError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "FILE_TOO_LARGE",
            f"Uploads are limited to {max_mb} MB. Import larger files with: "
            "python -m app.cli import-csv <path>",
        )
    filename = (file.filename or "upload.csv").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".csv"):
        raise AppError(422, "INVALID_CSV", "Only .csv files are accepted")

    batch = import_csv(db, file.file, filename, user)
    record_audit(
        db,
        actor=user,
        action="import.completed",
        entity_type="import_batch",
        entity_id=batch.id,
        after={
            "filename": batch.filename,
            "status": batch.status.value,
            "rows_total": batch.rows_total,
            "rows_inserted": batch.rows_inserted,
            "rows_duplicate": batch.rows_duplicate,
            "rows_rejected": batch.rows_rejected,
        },
        request=request,
    )
    db.commit()
    return batch


@router.get("", response_model=Page[ImportBatchRead], summary="Import history, newest first")
def list_imports(
    _: AnalystUser, db: DbSession, params: Annotated[PageParams, Depends()]
) -> Page[ImportBatchRead]:
    total = db.scalar(select(func.count()).select_from(ImportBatch)) or 0
    batches = db.scalars(
        select(ImportBatch)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    ).all()
    return Page[ImportBatchRead](
        items=[ImportBatchRead.model_validate(b) for b in batches],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get(
    "/{batch_id}",
    response_model=ImportBatchRead,
    summary="One import with its row-level errors",
    responses={404: {"model": ErrorResponse}},
)
def get_import(batch_id: int, _: AnalystUser, db: DbSession) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise not_found("Import", batch_id)
    return batch
