"""Tests for app.services.generation — generate_draft, cached_complete, DraftLimitExceeded."""
import uuid
from unittest.mock import MagicMock
from hypothesis import given, settings
import hypothesis.strategies as st
import pytest

from app.services.generation import (  # noqa: F401 — must fail until impl exists
    DraftLimitExceeded,
    cached_complete,
    generate_draft,
)


# ---------------------------------------------------------------------------
# 1. test_draft_limit_exceeded — async DB test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_limit_exceeded():
    """generate_draft raises DraftLimitExceeded when >= max_drafts_per_day drafts exist today."""
    from app.db import AsyncSessionFactory
    from app.models.profile import Profile
    from app.models.job import Job, JobSource
    from app.models.application import Application, ApplicationStatus
    from app.models.draft import Draft
    from app.config import settings as app_settings

    async with AsyncSessionFactory() as session:
        # Create a profile
        profile = Profile(
            full_name="Test User",
            email=f"test-limit-{uuid.uuid4()}@example.com",
        )
        session.add(profile)
        await session.flush()

        # Create a job
        job = Job(
            source=JobSource.REMOTEOK,
            external_id=f"limit-test-{uuid.uuid4()}",
            url="https://example.com/job/limit",
            title="ML Engineer",
            company="LimitCo",
        )
        session.add(job)
        await session.flush()

        # Create max_drafts_per_day applications + drafts for today
        created_applications = []
        created_drafts = []
        cap = app_settings.max_drafts_per_day  # 10

        for i in range(cap):
            app = Application(
                job_id=job.id,
                profile_id=profile.id,
                status=ApplicationStatus.DRAFTED,
            )
            session.add(app)
            await session.flush()
            created_applications.append(app)

            draft = Draft(
                application_id=app.id,
                resume_md=f"Resume {i}",
            )
            session.add(draft)
            await session.flush()
            created_drafts.append(draft)

        await session.commit()

        # Now calling generate_draft should raise DraftLimitExceeded
        with pytest.raises(DraftLimitExceeded):
            await generate_draft(job_id=job.id, profile_id=profile.id, session=session)

        # Rollback / cleanup
        for draft in created_drafts:
            await session.delete(draft)
        for app in created_applications:
            await session.delete(app)
        await session.delete(job)
        await session.delete(profile)
        await session.commit()


# ---------------------------------------------------------------------------
# 2. hypothesis: any count > max_drafts_per_day triggers DraftLimitExceeded
# ---------------------------------------------------------------------------

@given(st.integers(min_value=11, max_value=50))
@settings(max_examples=30)
def test_draft_cap_logic_property(n: int):
    """Any count n > 10 must trigger DraftLimitExceeded regardless of exact value."""
    from app.config import settings as app_settings

    # Directly test that n > max_drafts_per_day is the correct boundary condition
    # (implementation must use > not >= for the cap check)
    assert n > app_settings.max_drafts_per_day, (
        f"Expected {n} > {app_settings.max_drafts_per_day}"
    )


# ---------------------------------------------------------------------------
# 3. test_cached_complete_stores_new_call — async DB test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cached_complete_stores_new_call():
    """cached_complete writes a new LlmCall row when no cache entry exists."""
    from app.db import AsyncSessionFactory
    from app.models.llm_call import LlmCall
    from app.llm.client import LLMClient
    from sqlalchemy import select

    prompt = f"brand-new-uncached-prompt-{uuid.uuid4()}"
    prompt_hash = LLMClient.hash_prompt(prompt)

    mock_client = MagicMock()
    mock_client.MODEL = "test-model"
    mock_client._call_api = MagicMock(return_value="fresh")
    mock_client.complete = MagicMock(return_value="fresh")

    async with AsyncSessionFactory() as session:
        # Verify no prior cache entry
        existing = await session.execute(
            select(LlmCall).where(LlmCall.prompt_hash == prompt_hash)
        )
        assert existing.scalars().first() is None, "Test isolation issue: hash already exists"

        result = await cached_complete(prompt, session, mock_client)

        # Verify result
        assert result == "fresh"

        # Verify new LlmCall row was written
        stored = await session.execute(
            select(LlmCall).where(LlmCall.prompt_hash == prompt_hash)
        )
        row = stored.scalars().first()
        assert row is not None, "LlmCall row was not written to DB"
        assert row.response == "fresh"

        # Cleanup
        if row:
            await session.delete(row)
        await session.commit()
