from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class SourceRate(BaseModel):
    source: str
    sent_count: int
    responded_count: int
    response_rate: Optional[float]


class PromptRate(BaseModel):
    prompt_version: Optional[str]
    sent_count: int
    responded_count: int
    response_rate: Optional[float]


@router.get("/source-rates", response_model=list[SourceRate])
async def source_rates(db: AsyncSession = Depends(get_db)) -> list[SourceRate]:
    result = await db.execute(
        text("SELECT source, sent_count, responded_count, response_rate FROM v_response_rate_by_source")
    )
    return [
        SourceRate(
            source=row.source,
            sent_count=row.sent_count,
            responded_count=row.responded_count,
            response_rate=row.response_rate,
        )
        for row in result.fetchall()
    ]


@router.get("/prompt-rates", response_model=list[PromptRate])
async def prompt_rates(db: AsyncSession = Depends(get_db)) -> list[PromptRate]:
    result = await db.execute(
        text(
            "SELECT prompt_version, sent_count, responded_count, response_rate"
            " FROM v_response_rate_by_prompt_version"
        )
    )
    return [
        PromptRate(
            prompt_version=row.prompt_version,
            sent_count=row.sent_count,
            responded_count=row.responded_count,
            response_rate=row.response_rate,
        )
        for row in result.fetchall()
    ]
