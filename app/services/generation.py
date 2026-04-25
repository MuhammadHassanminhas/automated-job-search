from __future__ import annotations

import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.generator.cold_email import build_cold_email_prompt, parse_cold_email
from app.generator.cover_letter import build_cover_letter_prompt
from app.generator.resume import build_resume_prompt
from app.llm import make_llm_client
from app.llm.client import LLMClient
from app.llm.groq_client import GroqClient
from app.models.application import Application, ApplicationStatus
from app.models.draft import Draft
from app.models.job import Job
from app.models.llm_call import LlmCall
from app.models.profile import Profile


class DraftLimitExceeded(Exception):
    """Raised when the daily draft cap has been reached."""


async def cached_complete(
    prompt: str,
    session: AsyncSession,
    client: LLMClient,
) -> str:
    """Return a cached LLM response when available; otherwise call the API and cache the result."""
    prompt_hash = LLMClient.hash_prompt(prompt)

    row = await session.scalar(
        select(LlmCall).where(LlmCall.prompt_hash == prompt_hash).limit(1)
    )
    if row is not None and row.response is not None:
        return row.response

    t0 = time.monotonic()
    result = client.complete(prompt)
    latency = int((time.monotonic() - t0) * 1000)

    model_name: str = getattr(client, "MODEL", "unknown")
    call = LlmCall(
        provider="groq",
        model=model_name,
        prompt_hash=prompt_hash,
        prompt=prompt,
        response=result,
        latency_ms=latency,
    )
    session.add(call)
    await session.flush()
    return result


async def generate_draft(
    job_id: uuid.UUID,
    profile_id: uuid.UUID,
    session: AsyncSession,
) -> Draft:
    """Generate resume, cover letter, and cold email drafts for a job/profile pair."""
    # 1. Enforce daily cap
    today_start = func.date_trunc("day", func.now())
    draft_count = await session.scalar(
        select(func.count(Draft.id)).where(Draft.created_at >= today_start)
    )
    if (draft_count or 0) >= settings.max_drafts_per_day:
        raise DraftLimitExceeded(
            f"Daily draft limit of {settings.max_drafts_per_day} reached."
        )

    # 2. Load Job and Profile
    job = await session.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    profile = await session.scalar(select(Profile).where(Profile.id == profile_id))
    if profile is None:
        raise ValueError(f"Profile {profile_id} not found")

    skills: list[str] = profile.skills or []
    client = make_llm_client()

    # 3. Build prompts and call LLM (with caching)
    resume_prompt = build_resume_prompt(
        base_md=profile.base_resume_md or "",
        job_title=job.title,
        company=job.company,
        skills=skills,
    )
    resume_md = await cached_complete(resume_prompt, session, client)

    cl_prompt = build_cover_letter_prompt(
        job_title=job.title,
        company=job.company,
        matched_skills=skills,
    )
    cover_letter_md = await cached_complete(cl_prompt, session, client)

    email_prompt = build_cold_email_prompt(
        job_title=job.title,
        company=job.company,
    )
    email_raw = await cached_complete(email_prompt, session, client)
    email_subject, email_body = parse_cold_email(email_raw)

    # 4. Persist Application and Draft
    application = Application(
        job_id=job_id,
        profile_id=profile_id,
        status=ApplicationStatus.DRAFTED,
    )
    session.add(application)
    await session.flush()

    draft = Draft(
        application_id=application.id,
        resume_md=resume_md,
        cover_letter_md=cover_letter_md,
        email_subject=email_subject,
        email_body=email_body,
        model_used=GroqClient.MODEL,
        prompt_version="v1",
    )
    session.add(draft)
    await session.commit()

    return draft
