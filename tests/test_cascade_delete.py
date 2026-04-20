"""
A.1 cascade delete test — removing a profile cascades to its applications.
Fails at collection with ModuleNotFoundError('app') until app/ exists.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.profile import Profile  # ModuleNotFoundError until app/ exists
from app.models.application import Application
from app.db import AsyncSessionFactory


pytestmark = pytest.mark.asyncio


async def test_cascade_delete_applications_when_profile_removed() -> None:
    async with AsyncSessionFactory() as session:
        profile = Profile(
            full_name="Test Student",
            email="student@example.com",
            phone="+92-300-0000000",
        )
        session.add(profile)
        await session.flush()

        application = Application(
            profile_id=profile.id,
            status="DRAFTED",
        )
        session.add(application)
        await session.flush()

        application_id = application.id
        await session.delete(profile)
        await session.flush()

        result = await session.execute(
            select(Application).where(Application.id == application_id)
        )
        assert result.scalar_one_or_none() is None, (
            "Application should have been cascade-deleted with its profile"
        )
        await session.rollback()


@pytest.mark.parametrize("n_apps", [1, 5, 20])
async def test_cascade_delete_multiple_applications(n_apps: int) -> None:
    async with AsyncSessionFactory() as session:
        profile = Profile(
            full_name=f"Student {n_apps}",
            email=f"student{n_apps}@example.com",
        )
        session.add(profile)
        await session.flush()

        for i in range(n_apps):
            session.add(Application(profile_id=profile.id, status="DRAFTED"))
        await session.flush()

        await session.delete(profile)
        await session.flush()

        result = await session.execute(
            select(Application).where(Application.profile_id == profile.id)
        )
        remaining = result.scalars().all()
        assert len(remaining) == 0, f"Expected 0 remaining, got {len(remaining)}"
        await session.rollback()
