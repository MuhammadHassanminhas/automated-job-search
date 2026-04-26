"""B.3 failing tests — session cookie Secure flag based on environment.

Tests:
- In production env, POST /api/auth/login sets a cookie with Secure flag.
- In development env, the Set-Cookie header does NOT contain Secure flag.
- Property: cookie attribute strings always satisfy the env-based constraint.
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st

from app.auth.session import hash_password
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(email: str, password: str) -> User:
    """Build an in-memory User with a valid password hash (no DB needed)."""
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
    )


@pytest.fixture
def user_credentials() -> dict:
    return {"email": "cookietest@example.com", "password": "SecurePass123!"}


@pytest.fixture
def seeded_user(user_credentials: dict) -> User:
    return _make_user(
        email=user_credentials["email"],
        password=user_credentials["password"],
    )


# ---------------------------------------------------------------------------
# Test: production env → Secure flag present
# ---------------------------------------------------------------------------


class TestSecureCookieInProduction:
    """In production, the session cookie must carry the Secure flag."""

    def test_login_sets_secure_cookie_in_production(
        self, seeded_user: User, user_credentials: dict
    ) -> None:
        from app.main import app as fastapi_app
        from app.db import get_db
        import app.config as config_module

        mock_db = MagicMock()
        mock_db.scalar = AsyncMock(return_value=seeded_user)
        mock_db.commit = AsyncMock()

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield mock_db

        original_env = config_module.settings.env
        fastapi_app.dependency_overrides[get_db] = _fake_db
        config_module.settings.env = "production"
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.post("/api/auth/login", json=user_credentials)
                assert resp.status_code == 200, f"Login failed: {resp.text}"
                set_cookie_headers = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [
                    v for k, v in resp.headers.items() if k.lower() == "set-cookie"
                ]
                assert set_cookie_headers, "No Set-Cookie header found in response"
                cookie_str = " ".join(set_cookie_headers)
                assert "Secure" in cookie_str, (
                    f"Expected 'Secure' flag in Set-Cookie for production env, got: {cookie_str!r}"
                )
        finally:
            config_module.settings.env = original_env
            fastapi_app.dependency_overrides.clear()

    def test_session_cookie_name_present_in_production(
        self, seeded_user: User, user_credentials: dict
    ) -> None:
        from app.main import app as fastapi_app
        from app.db import get_db
        import app.config as config_module

        mock_db = MagicMock()
        mock_db.scalar = AsyncMock(return_value=seeded_user)
        mock_db.commit = AsyncMock()

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield mock_db

        original_env = config_module.settings.env
        fastapi_app.dependency_overrides[get_db] = _fake_db
        config_module.settings.env = "production"
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.post("/api/auth/login", json=user_credentials)
                assert resp.status_code == 200
                assert "session" in resp.cookies
        finally:
            config_module.settings.env = original_env
            fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test: development env → Secure flag absent
# ---------------------------------------------------------------------------


class TestNonSecureCookieInDevelopment:
    """In development, the session cookie must NOT carry the Secure flag."""

    def test_login_does_not_set_secure_cookie_in_development(
        self, seeded_user: User, user_credentials: dict
    ) -> None:
        from app.main import app as fastapi_app
        from app.db import get_db
        import app.config as config_module

        mock_db = MagicMock()
        mock_db.scalar = AsyncMock(return_value=seeded_user)
        mock_db.commit = AsyncMock()

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield mock_db

        original_env = config_module.settings.env
        fastapi_app.dependency_overrides[get_db] = _fake_db
        config_module.settings.env = "development"
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.post("/api/auth/login", json=user_credentials)
                assert resp.status_code == 200, f"Login failed: {resp.text}"
                set_cookie_headers = [
                    v for k, v in resp.headers.items() if k.lower() == "set-cookie"
                ]
                assert set_cookie_headers, "No Set-Cookie header found"
                cookie_str = " ".join(set_cookie_headers)
                # In development, "Secure" must NOT appear as a cookie attribute
                # (Note: case-sensitive per RFC 6265)
                cookie_attributes = [
                    part.strip() for part in cookie_str.split(";")
                ]
                secure_attrs = [a for a in cookie_attributes[1:] if a.lower() == "secure"]
                assert not secure_attrs, (
                    f"Did not expect 'Secure' flag in development env, got: {cookie_str!r}"
                )
        finally:
            config_module.settings.env = original_env
            fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Property test: cookie attribute strings satisfy env-based constraint
# ---------------------------------------------------------------------------


@given(env=st.sampled_from(["production", "development", "staging", "test"]))
@h_settings(max_examples=20)
def test_cookie_secure_flag_matches_env(env: str) -> None:
    """Property: Secure flag in Set-Cookie always matches whether env == 'production'."""
    from app.main import app as fastapi_app
    from app.db import get_db
    import app.config as config_module

    password = "PropTestPass123!"
    user = _make_user(email=f"prop_{uuid.uuid4().hex[:6]}@example.com", password=password)

    mock_db = MagicMock()
    mock_db.scalar = AsyncMock(return_value=user)
    mock_db.commit = AsyncMock()

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield mock_db

    original_env = config_module.settings.env
    fastapi_app.dependency_overrides[get_db] = _fake_db
    config_module.settings.env = env
    try:
        with TestClient(fastapi_app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/auth/login",
                json={"email": user.email, "password": password},
            )
            if resp.status_code != 200:
                return  # skip if login fails for any reason
            set_cookie_headers = [
                v for k, v in resp.headers.items() if k.lower() == "set-cookie"
            ]
            if not set_cookie_headers:
                return
            cookie_str = " ".join(set_cookie_headers)
            attrs = [part.strip() for part in cookie_str.split(";")]
            has_secure = any(a.lower() == "secure" for a in attrs[1:])
            if env == "production":
                assert has_secure, (
                    f"env={env!r}: expected Secure flag, got: {cookie_str!r}"
                )
            else:
                assert not has_secure, (
                    f"env={env!r}: did NOT expect Secure flag, got: {cookie_str!r}"
                )
    finally:
        config_module.settings.env = original_env
        fastapi_app.dependency_overrides.clear()
