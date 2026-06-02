# API маршруты для документов
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.document import Document, DocumentVersion
from app.models.user import User, UserRole
from app.models.project import ProjectMember
from app.middleware.auth import get_current_user
from app.services.s3 import upload_file_to_s3
from app.dependencies import get_project_member_by_iteration
from app.models.iteration import Iteration

router = APIRouter(prefix="/documents", tags=["Документы"])


async def _check_doc_membership(doc: Document, user: User, db: AsyncSession):
    """Verify user has project access via document's iteration"""
    if user.role == UserRole.ADMIN:
        return
    iter_result = await db.execute(select(Iteration).where(Iteration.id == doc.iteration_id))
    iteration = iter_result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    member_result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")


class DocumentCreate(BaseModel):
    iteration_id: str
    filename: str
    description: Optional[str] = None


@router.get("/iteration/{iteration_id}")
async def list_documents(
    iteration_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Список документов итерации"""
    result = await db.execute(
        select(Document)
        .where(Document.iteration_id == uuid.UUID(iteration_id))
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    items = []
    for d in docs:
        # Получаем последнюю версию
        ver_result = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == d.id)
            .order_by(DocumentVersion.version.desc())
        )
        latest = ver_result.scalars().first()
        items.append({
            "id": str(d.id),
            "filename": d.filename,
            "description": d.description,
            "current_version": d.current_version,
            "uploader_id": str(d.uploader_id),
            "file_url": latest.file_url if latest else None,
            "file_size": latest.file_size if latest else None,
            "mime_type": latest.mime_type if latest else None,
            "created_at": str(d.created_at),
            "updated_at": str(d.updated_at),
        })
    return items


@router.post("/upload", status_code=201)
async def upload_document(
    iteration_id: str = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Загрузка нового документа"""
    if not iteration_id:
        raise HTTPException(status_code=400, detail="iteration_id обязателен")

    # Verify project membership
    if user.role != UserRole.ADMIN:
        from app.models.iteration import Iteration
        iter_result = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(iteration_id)))
        iteration = iter_result.scalar_one_or_none()
        if not iteration:
            raise HTTPException(status_code=404, detail="Итерация не найдена")
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")

    url = await upload_file_to_s3(file, f"documents/{iteration_id}")

    doc = Document(
        iteration_id=uuid.UUID(iteration_id),
        filename=file.filename,
        uploader_id=user.id,
        current_version=1,
    )
    db.add(doc)
    await db.flush()

    version = DocumentVersion(
        document_id=doc.id,
        version=1,
        file_url=url,
        file_size=file.size,
        mime_type=file.content_type,
        uploader_id=user.id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(doc)
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_url": url,
    }


@router.post("/{document_id}/version", status_code=201)
async def upload_new_version(
    document_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Загрузка новой версии документа"""
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")

    await _check_doc_membership(doc, user, db)

    url = await upload_file_to_s3(file, f"documents/{doc.iteration_id}")
    new_ver = doc.current_version + 1
    doc.current_version = new_ver
    doc.filename = file.filename

    version = DocumentVersion(
        document_id=doc.id,
        version=new_ver,
        file_url=url,
        file_size=file.size,
        mime_type=file.content_type,
        uploader_id=user.id,
    )
    db.add(version)
    await db.commit()
    return {"version": new_ver, "file_url": url}


@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """История версий документа"""
    doc_result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    await _check_doc_membership(doc, user, db)

    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == uuid.UUID(document_id))
        .order_by(DocumentVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "file_url": v.file_url,
            "file_size": v.file_size,
            "mime_type": v.mime_type,
            "created_at": str(v.created_at),
        }
        for v in versions
    ]


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Удаление документа"""
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    await _check_doc_membership(doc, user, db)
    if doc.uploader_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Нет доступа")
    await db.delete(doc)
    await db.commit()
    return {"message": "Документ удалён"}


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Скачивание документа (редирект на S3 URL)"""
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    await _check_doc_membership(doc, user, db)
    ver_result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version.desc())
    )
    latest = ver_result.scalars().first()
    if not latest or not latest.file_url:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return RedirectResponse(url=latest.file_url)


@router.post("/collect-from-chat/{iteration_id}", status_code=200)
async def collect_chat_files(
    iteration_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: ProjectMember = Depends(get_project_member_by_iteration),
):
    """Автосбор файлов из чата итерации в Документы (ТЗ 3.11.2)"""
    from app.models.chat import ChatMessage
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.iteration_id == uuid.UUID(iteration_id))
        .where(ChatMessage.file_url.isnot(None))
        .where(ChatMessage.is_deleted == False)
    )
    messages = result.scalars().all()
    added = 0
    for msg in messages:
        # Check if already exists
        existing = await db.execute(
            select(Document)
            .where(Document.iteration_id == uuid.UUID(iteration_id))
            .where(Document.filename == msg.file_name)
        )
        if existing.scalar_one_or_none():
            continue
        doc = Document(
            iteration_id=uuid.UUID(iteration_id),
            filename=msg.file_name or f"chat_file_{msg.id}",
            description=f"Автоматически собрано из чата",
            uploader_id=msg.user_id,
            current_version=1,
        )
        db.add(doc)
        await db.flush()
        ver = DocumentVersion(
            document_id=doc.id,
            version=1,
            file_url=msg.file_url,
            file_size=msg.file_size,
            mime_type=msg.file_mime,
            uploader_id=msg.user_id,
        )
        db.add(ver)
        added += 1
    await db.commit()
    return {"message": f"Собрано {added} файлов из чата", "added": added}
