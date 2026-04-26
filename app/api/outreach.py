from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.models.outreach_event import OutreachEvent
from app.schemas.outreach import OutreachEventCreate, OutreachEventRead

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.get("", response_model=list[OutreachEventRead])
async def list_outreach_events(
    application_id: uuid.UUID | None = Query(default=None),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OutreachEvent]:
    stmt = select(OutreachEvent).order_by(OutreachEvent.created_at.desc())
    if application_id is not None:
        stmt = stmt.where(OutreachEvent.application_id == application_id)
    rows = await db.scalars(stmt)
    return list(rows.all())


@router.post("", response_model=OutreachEventRead, status_code=201)
async def create_outreach_event(
    body: OutreachEventCreate,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutreachEvent:
    event = OutreachEvent(**body.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
