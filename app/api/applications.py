from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db as get_session
from app.models.application import Application, ApplicationStatus
from app.models.job import Job
from app.models.user import User
from app.schemas.draft import ApplicationRead, ApplicationStatusPatch

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationRead])
async def list_applications(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[ApplicationRead]:
    result = await db.execute(
        select(Application, Job.title, Job.company)
        .outerjoin(Job, Application.job_id == Job.id)
        .order_by(Application.created_at.desc())
    )
    return [
        ApplicationRead(
            id=app.id,
            status=app.status.value,
            job_id=app.job_id,
            job_title=job_title,
            company=company,
            created_at=app.created_at,
        )
        for app, job_title, company in result.all()
    ]


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    result = await db.execute(
        select(Application, Job.title, Job.company)
        .outerjoin(Job, Application.job_id == Job.id)
        .where(Application.id == application_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    app, job_title, company = row
    return ApplicationRead(
        id=app.id,
        status=app.status.value,
        job_id=app.job_id,
        job_title=job_title,
        company=company,
        created_at=app.created_at,
    )


@router.patch("/{application_id}", response_model=ApplicationRead)
async def patch_application(
    application_id: uuid.UUID,
    body: ApplicationStatusPatch,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    app = await db.scalar(
        select(Application).where(Application.id == application_id)
    )
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    try:
        new_status = ApplicationStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {body.status!r}",
        )
    app.status = new_status
    await db.commit()
    await db.refresh(app)
    return ApplicationRead(
        id=app.id,
        status=app.status.value,
        job_id=app.job_id,
        created_at=app.created_at,
    )
