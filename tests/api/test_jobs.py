"""
A.4 jobs API tests — authenticated GET /api/jobs returns ranked list.
Fails at collection until app/api/jobs.py and app/schemas/job.py exist.
"""
from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings as h_settings
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app
from app.schemas.job import JobRead  # ImportError until impl


@pytest.fixture
async def auth_client(seeded_user_creds: dict):
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        await ac.post("/api/auth/login", json=seeded_user_creds)
        yield ac


async def test_get_jobs_returns_list(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


async def test_get_jobs_ordered_by_embedding_score(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    scores = [j.get("embedding_score") for j in jobs if j.get("embedding_score") is not None]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("limit", [1, 5, 20])
async def test_get_jobs_limit_param(auth_client: AsyncClient, limit: int) -> None:
    resp = await auth_client.get("/api/jobs", params={"limit": limit})
    assert resp.status_code == 200
    assert len(resp.json()) <= limit


@given(st.integers(min_value=0, max_value=200))
@h_settings(max_examples=10)
def test_jobs_limit_never_crashes(limit: int) -> None:
    import asyncio

    async def _run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/jobs", params={"limit": limit})
        assert resp.status_code in (200, 401, 422)

    asyncio.run(_run())
