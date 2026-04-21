"""
Shared fixtures for A.4 API tests.
Requires a running Postgres (docker compose up -d postgres).
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.session import hash_password  # ImportError until impl
from app.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.draft import Draft
from app.models.job import Job, JobSource
from app.models.user import User


TEST_EMAIL = "testuser@example.com"
TEST_PASSWORD = "TestPass123!"


async def _ensure_user(db: AsyncSession) -> User:
    existing = await db.scalar(select(User).where(User.email == TEST_EMAIL))
    if existing:
        return existing
    user = User(email=TEST_EMAIL, password_hash=hash_password(TEST_PASSWORD))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture(scope="session")
def seeded_user_creds() -> dict:
    return {"email": TEST_EMAIL, "password": TEST_PASSWORD}


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def _seeded_user(db_session: AsyncSession) -> User:
    return await _ensure_user(db_session)


@pytest.fixture
async def seeded_user(db_session: AsyncSession) -> User:
    return await _ensure_user(db_session)


@pytest.fixture
async def seeded_job_id(db_session: AsyncSession) -> uuid.UUID:
    job = Job(
        source=JobSource.REMOTEOK,
        external_id=f"test-{uuid.uuid4()}",
        url="https://remoteok.com/test",
        title="ML Engineer Intern",
        company="TestCo",
        location="Remote",
        remote_allowed=True,
        description="Build ML pipelines with Python and PyTorch.",
        hash=f"testhash-{uuid.uuid4().hex}",
        keyword_score=0.8,
        embedding_score=0.9,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job.id


@pytest.fixture
async def seeded_draft_id(db_session: AsyncSession, seeded_job_id: uuid.UUID) -> uuid.UUID:
    app_row = Application(
        job_id=seeded_job_id,
        status=ApplicationStatus.DRAFTED,
    )
    db_session.add(app_row)
    await db_session.flush()

    draft = Draft(
        application_id=app_row.id,
        resume_md="# Resume",
        cover_letter_md="Dear Hiring Team at TestCo,",
        email_subject="Internship Opportunity",
        email_body="Hello, I am interested.",
        model_used="test",
        prompt_version="v1",
    )
    db_session.add(draft)
    await db_session.commit()
    await db_session.refresh(draft)
    return draft.id
