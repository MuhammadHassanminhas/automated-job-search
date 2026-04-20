"""
A.1 vector nearest-neighbor test — 100 random 384-dim vectors inserted via ORM;
HNSW cosine query returns the exact same vector as nearest neighbor to itself.
Fails at collection with ModuleNotFoundError('app') until app/ exists.
"""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
import hypothesis.strategies as st
from sqlalchemy import text

from app.models.job import Job, JobSource  # ModuleNotFoundError until app/ exists
from app.db import AsyncSessionFactory


@pytest.mark.asyncio
async def test_hnsw_cosine_nearest_neighbor_self() -> None:
    rng = np.random.default_rng(seed=42)
    n = 100
    dims = 384
    vecs = rng.random((n, dims)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / np.where(norms == 0, 1.0, norms)

    async with AsyncSessionFactory() as session:
        job_ids = []
        for i, vec in enumerate(vecs):
            job = Job(
                source=JobSource.REMOTEOK,
                external_id=f"vec-selftest-{i}",
                title=f"Vector Test Job {i}",
                company="VecCo",
                url=f"https://example.com/vec/{i}",
                description_embedding=vec.tolist(),
            )
            session.add(job)
            await session.flush()
            job_ids.append(str(job.id))

        query_vec = vecs[0].tolist()
        vec_literal = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"
        result = await session.execute(
            text(
                f"SELECT id FROM jobs WHERE id = ANY(:ids) "
                f"ORDER BY description_embedding <=> '{vec_literal}'::vector LIMIT 1"
            ),
            {"ids": job_ids},
        )
        nearest_id = str(result.scalar_one())
        assert nearest_id == job_ids[0], (
            f"HNSW cosine nearest neighbor of vecs[0] should be itself, got {nearest_id}"
        )
        await session.rollback()


@given(st.integers(min_value=2, max_value=20))
@settings(max_examples=5)
def test_hnsw_query_returns_exactly_one_row(n: int) -> None:
    import asyncio

    async def _run() -> None:
        rng = np.random.default_rng(seed=n)
        vecs = rng.random((n, 384)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs = vecs / np.where(norms == 0, 1.0, norms)

        async with AsyncSessionFactory() as session:
            ids = []
            for i, vec in enumerate(vecs):
                job = Job(
                    source=JobSource.REMOTEOK,
                    external_id=f"vec-prop-{n}-{i}",
                    title=f"Prop Job {n}-{i}",
                    company="PropCo",
                    url=f"https://example.com/prop/{n}/{i}",
                    description_embedding=vec.tolist(),
                )
                session.add(job)
                await session.flush()
                ids.append(str(job.id))

            vec_literal = "[" + ",".join(f"{v:.8f}" for v in vecs[0].tolist()) + "]"
            result = await session.execute(
                text(
                    f"SELECT id FROM jobs WHERE id = ANY(:ids) "
                    f"ORDER BY description_embedding <=> '{vec_literal}'::vector LIMIT 1"
                ),
                {"ids": ids},
            )
            rows = result.fetchall()
            assert len(rows) == 1
            await session.rollback()

    asyncio.run(_run())
