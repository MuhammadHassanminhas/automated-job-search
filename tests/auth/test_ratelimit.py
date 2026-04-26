"""B.3 failing tests — rate limiting on auth endpoints.

Imports from app.auth.ratelimit (does NOT exist yet → ImportError at collection).

Tests:
- After 5 failed login attempts from same IP, the 6th returns 429.
- After 10 successful requests to any /api/auth/* route in <60s, the 11th returns 429.
- Property: sending N>10 requests always produces at least one 429.
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st
from polyfactory.factories.pydantic_factory import ModelFactory

from app.schemas.auth import LoginRequest


# ---------------------------------------------------------------------------
# polyfactory factory for LoginRequest
# ---------------------------------------------------------------------------


class LoginRequestFactory(ModelFactory):
    __model__ = LoginRequest

    email = lambda: f"user_{uuid.uuid4().hex[:8]}@example.com"  # noqa: E731
    password = lambda: f"Pass{uuid.uuid4().hex[:12]}!"  # noqa: E731


# ---------------------------------------------------------------------------
# DB mock helpers
# ---------------------------------------------------------------------------


def _make_mock_db() -> MagicMock:
    """Return a mock AsyncSession that always returns None for scalar queries."""
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


def _get_test_client_with_mock_db() -> TestClient:
    """Build a TestClient with the DB dependency overridden to avoid live DB."""
    from app.main import app as fastapi_app
    from app.db import get_db

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield _make_mock_db()

    fastapi_app.dependency_overrides[get_db] = _fake_db
    client = TestClient(fastapi_app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    from app.main import app as fastapi_app
    from app.db import get_db

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield _make_mock_db()

    fastapi_app.dependency_overrides[get_db] = _fake_db
    with TestClient(fastapi_app, raise_server_exceptions=False) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 1: 5 failed login attempts → 6th returns 429
# ---------------------------------------------------------------------------


class TestFailedLoginRateLimit:
    """After 5 consecutive failed login attempts from the same IP, the 6th must be 429."""

    def test_sixth_failed_login_returns_429(self, test_client: TestClient) -> None:
        bad_creds = {"email": "nobody@example.com", "password": "wrongpassword"}
        # First 5 attempts may return 401 (invalid creds) — the 6th must be 429
        statuses: list[int] = []
        for _ in range(6):
            resp = test_client.post(
                "/api/auth/login",
                json=bad_creds,
                headers={"X-Forwarded-For": "10.0.0.1"},
            )
            statuses.append(resp.status_code)
        # At least one 429 must appear after the threshold
        assert 429 in statuses, (
            f"Expected 429 after 5 failed attempts, got statuses: {statuses}"
        )

    def test_sixth_attempt_status_is_exactly_429(self, test_client: TestClient) -> None:
        bad_creds = {"email": "ratelimit_test@example.com", "password": "badpass"}
        headers = {"X-Forwarded-For": "10.0.0.2"}
        for _ in range(5):
            test_client.post("/api/auth/login", json=bad_creds, headers=headers)
        resp = test_client.post("/api/auth/login", json=bad_creds, headers=headers)
        assert resp.status_code == 429, (
            f"Expected 429 on 6th failed attempt, got {resp.status_code}"
        )

    def test_rate_limit_response_has_retry_after_or_detail(
        self, test_client: TestClient
    ) -> None:
        bad_creds = {"email": "rl_detail@example.com", "password": "badpass"}
        headers = {"X-Forwarded-For": "10.0.0.3"}
        for _ in range(5):
            test_client.post("/api/auth/login", json=bad_creds, headers=headers)
        resp = test_client.post("/api/auth/login", json=bad_creds, headers=headers)
        assert resp.status_code == 429
        # Response must convey limit information: either Retry-After header or JSON detail
        has_retry_after = "retry-after" in {k.lower() for k in resp.headers}
        has_detail = "detail" in resp.json() if resp.headers.get("content-type", "").startswith("application/json") else False
        assert has_retry_after or has_detail, (
            "429 response must include Retry-After header or JSON detail"
        )


# ---------------------------------------------------------------------------
# Test 2: 10 requests to any /api/auth/* in <60s → 11th returns 429
# ---------------------------------------------------------------------------


class TestAuthEndpointBurstRateLimit:
    """Sending more than 10 requests to /api/auth/* within 60s triggers 429."""

    def test_eleventh_auth_request_returns_429(self, test_client: TestClient) -> None:
        headers = {"X-Forwarded-For": "10.1.0.1"}
        statuses: list[int] = []
        for _ in range(11):
            resp = test_client.get("/api/auth/me", headers=headers)
            statuses.append(resp.status_code)
        assert 429 in statuses, (
            f"Expected 429 after 10 requests, got statuses: {statuses}"
        )

    def test_eleventh_login_burst_returns_429(self, test_client: TestClient) -> None:
        headers = {"X-Forwarded-For": "10.1.0.2"}
        bad_creds = {"email": "burst@example.com", "password": "anypass"}
        statuses: list[int] = []
        for _ in range(11):
            resp = test_client.post("/api/auth/login", json=bad_creds, headers=headers)
            statuses.append(resp.status_code)
        assert 429 in statuses, (
            f"Expected 429 after 10 auth requests, got statuses: {statuses}"
        )


# ---------------------------------------------------------------------------
# Property test: N > 10 requests → at least one 429
# ---------------------------------------------------------------------------


@given(st.integers(min_value=11, max_value=20))
@h_settings(max_examples=5)
def test_n_requests_above_threshold_produces_429(n: int) -> None:
    """Property: sending N>10 requests from same IP produces at least one 429."""
    from app.main import app as fastapi_app
    from app.db import get_db

    mock_db = _make_mock_db()

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield mock_db

    fastapi_app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(fastapi_app, raise_server_exceptions=False) as client:
            headers = {"X-Forwarded-For": f"10.2.{n}.1"}
            statuses: list[int] = []
            for _ in range(n):
                resp = client.get("/api/auth/me", headers=headers)
                statuses.append(resp.status_code)
            assert 429 in statuses, (
                f"N={n} requests did not produce any 429. Statuses: {statuses}"
            )
    finally:
        fastapi_app.dependency_overrides.clear()
