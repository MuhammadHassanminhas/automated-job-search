from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.ratelimit import limiter
from app.auth.session import create_session_cookie, verify_password
from app.config import settings
from app.db import get_db as get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> UserRead:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    cookie = create_session_cookie({"user_id": str(user.id), "email": user.email})
    secure = settings.env == "production"
    response.set_cookie("session", cookie, httponly=True, samesite="lax", secure=secure, max_age=60 * 60 * 24 * 7)
    return UserRead.model_validate(user)


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, response: Response) -> dict:
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/me")
@limiter.limit("10/minute")
async def me(request: Request, user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
