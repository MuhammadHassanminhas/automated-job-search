from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.gmail_oauth import GmailOAuth, exchange_code
from app.config import settings
from app.db import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth/gmail", tags=["auth:gmail"])


def _get_oauth_client() -> GmailOAuth:
    return GmailOAuth(
        client_id=settings.gmail_oauth_client_id,
        client_secret=settings.gmail_oauth_client_secret,
        redirect_uri=settings.gmail_oauth_redirect_uri,
    )


@router.get("/authorize")
async def gmail_authorize(
    _user: User = Depends(get_current_user),
) -> RedirectResponse:
    oauth = _get_oauth_client()
    state = str(uuid.uuid4())
    url = oauth.get_authorize_url(state=state)
    return RedirectResponse(url=url)


@router.get("/callback")
async def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await exchange_code(code=code, state=state, session=db, user_id=_user.id)
    return {"status": "ok"}
