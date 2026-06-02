# API экспорта в PDF
import io
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.database import get_db
from app.models.retrospective import Retrospective, RetrospectiveAnswer
from app.models.iteration import Iteration
from app.models.task import Task
from app.models.user import User, UserRole
from app.models.project import ProjectMember
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/export", tags=["Экспорт"])


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RuTitle', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle(name='RuHeading', fontSize=14, leading=18, spaceAfter=10, spaceBefore=10))
    styles.add(ParagraphStyle(name='RuBody', fontSize=10, leading=14, spaceAfter=6))
    return styles


@router.get("/retrospective/{iteration_id}")
async def export_retrospective_pdf(
    iteration_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Экспорт ретроспективы в PDF"""
    # Verify project membership
    iter_result = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(iteration_id)))
    iteration = iter_result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Итерация не найдена")
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")

    result = await db.execute(
        select(Retrospective)
        .options(selectinload(Retrospective.answers))
        .where(Retrospective.iteration_id == uuid.UUID(iteration_id))
    )
    retro = result.scalar_one_or_none()
    if not retro:
        raise HTTPException(status_code=404, detail="Retrospecitva not found")

    # Получаем информацию итерации
    iter_result = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(iteration_id)))
    iteration = iter_result.scalar_one_or_none()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = build_styles()
    story = []

    # Заголовок
    title = f"Retrospective: {iteration.name if iteration else iteration_id}"
    story.append(Paragraph(title, styles['RuTitle']))
    story.append(Paragraph(f"Date: {datetime.utcnow().strftime('%d.%m.%Y')}", styles['RuBody']))
    story.append(Spacer(1, 20))

    # Ответы
    for answer in retro.answers:
        u_result = await db.execute(select(User.name).where(User.id == answer.user_id))
        user_name = u_result.scalar_one_or_none() or "Unknown"

        story.append(Paragraph(f"Author: {user_name}", styles['RuHeading']))
        if answer.went_well:
            story.append(Paragraph(f"What went well: {answer.went_well}", styles['RuBody']))
        if answer.to_improve:
            story.append(Paragraph(f"What to improve: {answer.to_improve}", styles['RuBody']))
        if answer.to_try:
            story.append(Paragraph(f"What to try: {answer.to_try}", styles['RuBody']))
        story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)

    filename = f"retrospective_{iteration_id[:8]}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/iteration/{iteration_id}")
async def export_iteration_pdf(
    iteration_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Экспорт итерации с задачами в PDF"""
    iter_result = await db.execute(select(Iteration).where(Iteration.id == uuid.UUID(iteration_id)))
    iteration = iter_result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="Iteration not found")

    # Verify project membership
    if user.role != UserRole.ADMIN:
        member_result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == iteration.project_id, ProjectMember.user_id == user.id)
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не являетесь участником этого проекта")

    # Получаем задачи
    tasks_result = await db.execute(
        select(Task).where(Task.iteration_id == uuid.UUID(iteration_id)).order_by(Task.status, Task.priority)
    )
    tasks = tasks_result.scalars().all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = build_styles()
    story = []

    story.append(Paragraph(f"Iteration: {iteration.name}", styles['RuTitle']))
    story.append(Paragraph(
        f"Period: {iteration.start_date.strftime('%d.%m.%Y') if iteration.start_date else ''} - "
        f"{iteration.end_date.strftime('%d.%m.%Y') if iteration.end_date else ''}",
        styles['RuBody']
    ))
    story.append(Paragraph(f"Status: {iteration.status}", styles['RuBody']))
    story.append(Spacer(1, 20))

    # Таблица задач
    if tasks:
        data = [['Title', 'Status', 'Priority', 'Assignee']]
        for task in tasks:
            assignee = ""
            if task.assignee_id:
                u_res = await db.execute(select(User.name).where(User.id == task.assignee_id))
                assignee = u_res.scalar_one_or_none() or ""
            data.append([
                task.title[:40],
                task.status,
                task.priority,
                assignee,
            ])

        table = Table(data, colWidths=[7*cm, 4*cm, 3*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.2, 0.2)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ]))
        story.append(Paragraph("Tasks", styles['RuHeading']))
        story.append(table)

    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Total tasks: {len(tasks)}", styles['RuBody']))

    doc.build(story)
    buffer.seek(0)

    filename = f"iteration_{iteration_id[:8]}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
