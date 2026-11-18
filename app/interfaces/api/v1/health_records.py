"""Health Records: a personal drive with two folders, "prescriptions" and
"health_records" (lab reports, imaging, discharge summaries and other
documents). Files are PDFs or images."""
from datetime import date
from typing import List, Optional
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status,
)

from app.application.dto.health_dto import (
    FolderUsage, HealthRecordResponse, HealthRecordSummary, HealthRecordUpdateRequest,
)
from app.config import settings
from app.domain.entities.health_record import HealthRecord
from app.domain.services.file_types import ALLOWED_TYPES, sniff_content_type
from app.domain.value_objects.health_enums import RecordCategory, RecordFolder
from app.interfaces.api.deps import get_current_user, get_health_record_repository

router = APIRouter(prefix="/health-records", tags=["Health Records"])

_MB = 1024 * 1024


def _max_file_bytes() -> int:
    return settings.HEALTH_RECORD_MAX_FILE_MB * _MB


def _quota_bytes() -> int:
    return settings.HEALTH_RECORD_QUOTA_MB * _MB


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")


def _check_category(folder: RecordFolder, category: RecordCategory) -> None:
    if (folder == RecordFolder.PRESCRIPTIONS) != (category == RecordCategory.PRESCRIPTION):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prescriptions go in the 'prescriptions' folder; other documents "
                   "go in 'health_records'",
        )


def _safe_file_name(name: Optional[str], content_type: str) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    base = "".join(c for c in base if c.isprintable())[:200]
    if not base:
        base = "document"
    ext = ALLOWED_TYPES[content_type]
    if not base.lower().endswith("." + ext) and not (
            ext == "jpg" and base.lower().endswith(".jpeg")):
        base = f"{base}.{ext}"
    return base


@router.get("/summary", response_model=HealthRecordSummary,
            summary="File counts and storage used per folder")
async def summary(
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    usage = await repo.usage(current_user.id)
    folders = [
        FolderUsage(folder=f, count=usage.get(f.value, {}).get("count", 0),
                    bytes=usage.get(f.value, {}).get("bytes", 0))
        for f in RecordFolder
    ]
    return HealthRecordSummary(
        folders=folders,
        total_bytes=sum(f.bytes for f in folders),
        quota_bytes=_quota_bytes(),
        max_file_bytes=_max_file_bytes(),
    )


@router.get("", response_model=List[HealthRecordResponse],
            summary="List my records, newest document date first")
async def list_records(
    folder: Optional[RecordFolder] = Query(None),
    category: Optional[RecordCategory] = Query(None),
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    records = await repo.list(current_user.id, folder, category)
    return [HealthRecordResponse.from_entity(r) for r in records]


@router.post("", response_model=HealthRecordResponse, status_code=status.HTTP_201_CREATED,
             summary="Upload a PDF or image (multipart/form-data)")
async def upload_record(
    file: UploadFile = File(..., description="PDF, JPEG, PNG, WEBP or HEIC"),
    folder: RecordFolder = Form(...),
    category: Optional[RecordCategory] = Form(
        None, description="Defaults to 'prescription' or 'other' depending on the folder"),
    title: Optional[str] = Form(None, max_length=150),
    notes: Optional[str] = Form(None, max_length=2000),
    document_date: Optional[date] = Form(None, description="Date on the document"),
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    category = category or (RecordCategory.PRESCRIPTION
                            if folder == RecordFolder.PRESCRIPTIONS else RecordCategory.OTHER)
    _check_category(folder, category)

    max_bytes = _max_file_bytes()
    data = await file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Files can be up to {settings.HEALTH_RECORD_MAX_FILE_MB} MB",
        )
    content_type = sniff_content_type(data[:16])
    if content_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, JPEG, PNG, WEBP and HEIC files are supported",
        )

    usage = await repo.usage(current_user.id)
    used = sum(u["bytes"] for u in usage.values())
    if used + len(data) > _quota_bytes():
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Your Health Records storage is full "
                   f"({settings.HEALTH_RECORD_QUOTA_MB} MB). Delete some files first.",
        )

    file_name = _safe_file_name(file.filename, content_type)
    clean_title = (title or "").strip() or file_name.rsplit(".", 1)[0]
    record = await repo.create(HealthRecord(
        id=uuid4(),
        user_id=current_user.id,
        folder=folder,
        category=category,
        title=clean_title[:150],
        notes=(notes or "").strip() or None,
        document_date=document_date,
        file_name=file_name,
        content_type=content_type,
        size_bytes=len(data),
    ), data)
    return HealthRecordResponse.from_entity(record)


@router.get("/{record_id}", response_model=HealthRecordResponse, summary="One record's details")
async def get_record(
    record_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    record = await repo.get(current_user.id, record_id)
    if not record:
        raise _not_found()
    return HealthRecordResponse.from_entity(record)


@router.get("/{record_id}/file", summary="Download the file",
            responses={200: {"content": {"application/pdf": {}, "image/*": {}}}})
async def download_record(
    record_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    record = await repo.get(current_user.id, record_id)
    data = await repo.get_file(current_user.id, record_id) if record else None
    if not record or data is None:
        raise _not_found()
    return Response(
        content=data,
        media_type=record.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(record.file_name)}",
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{record_id}", response_model=HealthRecordResponse,
              summary="Rename, recategorise or annotate a record")
async def update_record(
    record_id: UUID,
    data: HealthRecordUpdateRequest,
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    record = await repo.get(current_user.id, record_id)
    if not record:
        raise _not_found()
    changes = data.model_dump(exclude_unset=True)
    if "title" in changes and not changes["title"]:
        raise HTTPException(status_code=422, detail="Title cannot be empty")
    for key, value in changes.items():
        setattr(record, key, value)
    _check_category(record.folder, record.category)
    return HealthRecordResponse.from_entity(await repo.update(record))


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a record and its file")
async def delete_record(
    record_id: UUID,
    current_user=Depends(get_current_user),
    repo=Depends(get_health_record_repository),
):
    if not await repo.delete(current_user.id, record_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
