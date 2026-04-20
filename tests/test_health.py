"""
A.1 health endpoint tests — GET /health shape, 200 OK, 503 on DB failure,
and hypothesis property test for query-param stability.
Fails at collection with ModuleNotFoundError('app') until app/ exists.
"""
from __future__ import annotations

import asyncio

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from httpx import AsyncClient

from app.main import app as fastapi_app  # ModuleNotFoundError until app/ exists


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


async def test_health_200(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert {"status", "db", "version"} <= set(body.keys())
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert isinstance(body["version"], str) and body["version"]


async def test_health_503_when_db_down(monkeypatch) -> None:
    from app import db as app_db  # noqa: PLC0415

    async def _broken():
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(app_db, "check_connection", _broken, raising=False)
    async with AsyncClient(app=fastapi_app, base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["db"] != "ok"
    assert body["status"] != "ok"


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N"))),
        st.text(max_size=25),
        max_size=6,
    )
)
@settings(max_examples=20)
def test_health_shape_stable_under_arbitrary_query_params(params: dict) -> None:
    async def _run() -> None:
        async with AsyncClient(app=fastapi_app, base_url="http://test") as c:
            resp = await c.get("/health", params=params)
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body
        assert "db" in body
        assert "version" in body

    asyncio.run(_run())
