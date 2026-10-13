from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.api.dependencies import require_roles
from app.db.models import Equipment, Laboratory, User, UserRole
from app.db.session import get_db
from app.modules.document_ingestion import safe_filename, read_upload, save_uploaded_document


def create_documents_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

    @router.post("", status_code=201)
    async def upload_document(
        file: UploadFile = File(...),
        equipment_code: Optional[str] = Form(default=None, max_length=64),
        title: Optional[str] = Form(default=None, max_length=255),
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    ) -> dict:
        filename = safe_filename(file.filename)
        normalized_equipment_code = (equipment_code or "").strip() or None
        equipment = None
        if normalized_equipment_code:
            equipment = await session.scalar(
                select(Equipment).where(Equipment.equipment_code == normalized_equipment_code)
            )
            if equipment is None:
                raise HTTPException(status_code=404, detail="设备不存在。")
            if current_user.role is UserRole.TEACHER and current_user.college_id is not None:
                managed = await session.scalar(
                    select(Equipment.id)
                    .join(Equipment.laboratory)
                    .where(
                        Equipment.id == equipment.id,
                        Laboratory.manager_teacher_id == current_user.id,
                    )
                )
                if managed is None:
                    raise HTTPException(status_code=404, detail="设备不存在或无权访问。")

        content = await read_upload(file, settings.document_upload_max_bytes)
        document, chunk_count, duplicate = await save_uploaded_document(
            session,
            equipment=equipment,
            filename=filename,
            title=title,
            content=content,
            storage_path=settings.document_storage_path,
            uploaded_by_id=current_user.id,
        )
        return {
            "id": document.id,
            "filename": document.filename,
            "title": document.title,
            "equipment_code": document.equipment_code,
            "status": document.processing_status.name.lower(),
            "chunk_count": chunk_count,
            "duplicate": duplicate,
        }

    return router
