from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db as get_session
from app.models.application import Application, ApplicationStatus
from app.models.draft import Draft
from app.models.profile import Profile
from app.models.user import User
from app.schemas.draft import ApplicationRead, DraftPatch, DraftRead
from app.services.generation import DraftLimitExceeded, generate_draft

router = APIRouter(prefix="/api/drafts", tags=["drafts"])

_VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DRAFTED: {ApplicationStatus.APPROVED, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.APPROVED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}


async def _get_draft_or_404(draft_id: uuid.UUID, db: AsyncSession) -> Draft:
    draft = await db.scalar(select(Draft).where(Draft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


async def _get_application_or_404(app_id: uuid.UUID, db: AsyncSession) -> Application:
    app = await db.scalar(select(Application).where(Application.id == app_id))
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


async def _transition(
    draft_id: uuid.UUID,
    target: ApplicationStatus,
    db: AsyncSession,
) -> ApplicationRead:
    draft = await _get_draft_or_404(draft_id, db)
    application = await _get_application_or_404(draft.application_id, db)

    if target not in _VALID_TRANSITIONS.get(application.status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from {application.status} to {target}",
        )

    application.status = target
    await db.commit()
    await db.refresh(application)
    return ApplicationRead.model_validate(application)


@router.post("/generate/{job_id}", response_model=DraftRead, status_code=201)
async def generate(
    job_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DraftRead:
    profile = await db.scalar(select(Profile).limit(1))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No profile found — run `profile import` first",
        )
    try:
        draft = await generate_draft(job_id=job_id, profile_id=profile.id, session=db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DraftLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    return DraftRead.model_validate(draft)


@router.get("/{draft_id}", response_model=DraftRead)
async def get_draft(
    draft_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DraftRead:
    draft = await _get_draft_or_404(draft_id, db)
    return DraftRead.model_validate(draft)


@router.patch("/{draft_id}", response_model=DraftRead)
async def patch_draft(
    draft_id: uuid.UUID,
    body: DraftPatch,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DraftRead:
    draft = await _get_draft_or_404(draft_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(draft, field, value)
    await db.commit()
    await db.refresh(draft)
    return DraftRead.model_validate(draft)


@router.post("/{draft_id}/approve", response_model=ApplicationRead)
async def approve(
    draft_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    return await _transition(draft_id, ApplicationStatus.APPROVED, db)


@router.post("/{draft_id}/reject", response_model=ApplicationRead)
async def reject(
    draft_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    return await _transition(draft_id, ApplicationStatus.WITHDRAWN, db)
