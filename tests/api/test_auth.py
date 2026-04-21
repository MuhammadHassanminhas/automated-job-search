"""
A.4 auth tests — 401 on unauthenticated access, login/logout/me round-trip.
Fails at collection until app/auth/session.py and app/api/auth.py exist.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app  # exists; new routes wired in impl
from app.auth.session import create_session_cookie, decode_session_cookie  # ImportError until impl


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        yield ac


# ── unauthenticated access ────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("GET",   "/api/drafts/00000000-0000-0000-0000-000000000001"),
    ("PATCH", "/api/drafts/00000000-0000-0000-0000-000000000001"),
    ("POST",  "/api/drafts/00000000-0000-0000-0000-000000000001/approve"),
    ("POST",  "/api/drafts/00000000-0000-0000-0000-000000000001/reject"),
    ("GET",   "/api/jobs"),
])
async def test_unauthenticated_returns_401(client: AsyncClient, method: str, path: str) -> None:
    resp = await client.request(method, path)
    assert resp.status_code == 401


# ── login / logout / me ───────────────────────────────────────────────────────

async def test_login_bad_credentials_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_login_sets_session_cookie(client: AsyncClient, seeded_user_creds: dict) -> None:
    resp = await client.post("/api/auth/login", json=seeded_user_creds)
    assert resp.status_code == 200
    assert "session" in resp.cookies


async def test_me_after_login_returns_email(client: AsyncClient, seeded_user_creds: dict) -> None:
    await client.post("/api/auth/login", json=seeded_user_creds)
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == seeded_user_creds["email"]


async def test_me_after_logout_returns_401(client: AsyncClient, seeded_user_creds: dict) -> None:
    await client.post("/api/auth/login", json=seeded_user_creds)
    await client.post("/api/auth/logout")
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


# ── session cookie helpers ────────────────────────────────────────────────────

def test_session_cookie_roundtrip() -> None:
    """create_session_cookie → decode_session_cookie returns original payload."""
    payload = {"user_id": "abc-123", "email": "test@example.com"}
    cookie = create_session_cookie(payload)
    decoded = decode_session_cookie(cookie)
    assert decoded["user_id"] == payload["user_id"]
    assert decoded["email"] == payload["email"]


def test_tampered_cookie_raises() -> None:
    from app.auth.session import InvalidSession  # ImportError until impl
    cookie = create_session_cookie({"user_id": "x"})
    tampered = cookie[:-4] + "XXXX"
    with pytest.raises(InvalidSession):
        decode_session_cookie(tampered)
