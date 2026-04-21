from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db as get_session
from app.models.application import Application
from app.models.user import User
from app.schemas.draft import ApplicationRead

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationRead])
async def list_applications(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[Application]:
    rows = await db.scalars(select(Application).order_by(Application.created_at.desc()))
    return list(rows.all())


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> Application:
    app = await db.scalar(select(Application).where(Application.id == application_id))
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app
