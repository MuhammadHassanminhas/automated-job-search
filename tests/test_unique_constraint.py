"""
A.1 DB constraint test — unique (source, external_id) on jobs raises IntegrityError.
Fails at collection with ModuleNotFoundError('app') until app/ exists.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.job import Job, JobSource  # ModuleNotFoundError until app/ exists
from app.db import AsyncSessionFactory


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("source,ext_id", [
    ("REMOTEOK", "dup-001"),
    ("INTERNSHALA", "dup-002"),
    ("ROZEE", "dup-003"),
])
async def test_unique_source_external_id_constraint(
    source: str, ext_id: str
) -> None:
    async with AsyncSessionFactory() as session:
        job1 = Job(
            source=JobSource(source),
            external_id=ext_id,
            title="ML Intern",
            company="Acme",
            url="https://example.com/1",
        )
        job2 = Job(
            source=JobSource(source),
            external_id=ext_id,
            title="Different Title",
            company="Other Corp",
            url="https://example.com/2",
        )
        session.add(job1)
        await session.flush()
        session.add(job2)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
