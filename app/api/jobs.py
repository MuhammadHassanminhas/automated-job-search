from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db as get_session
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobRead

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(
    limit: int = Query(default=50, ge=0, le=200),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[Job]:
    rows = await db.scalars(
        select(Job)
        .order_by(Job.embedding_score.desc().nulls_last())
        .limit(limit)
    )
    return list(rows.all())
