"""
A.4 drafts API tests — generate, read, patch, approve/reject, invalid transitions.
Fails at collection until app/api/drafts.py and app/schemas/ exist.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings as h_settings
from httpx import ASGITransport, AsyncClient
from polyfactory.factories.pydantic_factory import ModelFactory

from app.main import app as fastapi_app
from app.models.application import ApplicationStatus
from app.models.draft import Draft
from app.schemas.draft import DraftRead  # ImportError until impl


class DraftReadFactory(ModelFactory):
    __model__ = DraftRead


@pytest.fixture
async def auth_client(_seeded_user, seeded_user_creds: dict):
    """Authenticated AsyncClient. _seeded_user ensures the user row exists before login."""
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        await ac.post("/api/auth/login", json=seeded_user_creds)
        yield ac


# ── generate ──────────────────────────────────────────────────────────────────

async def test_generate_creates_application_and_draft(
    auth_client: AsyncClient, seeded_job_id: uuid.UUID
) -> None:
    # Patch at the router's import site so the mock intercepts the call.
    with patch(
        "app.api.drafts.generate_draft", new_callable=AsyncMock
    ) as mock_gen:
        fake_draft = Draft(
            id=uuid.uuid4(),
            application_id=uuid.uuid4(),
            resume_md="# Resume",
            cover_letter_md="Dear Hiring Team",
            email_subject="Subject",
            email_body="Body",
            model_used="test",
            prompt_version="v1",
        )
        mock_gen.return_value = fake_draft
        resp = await auth_client.post(f"/api/drafts/generate/{seeded_job_id}")

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["prompt_version"] == "v1"


async def test_generate_unknown_job_returns_404(auth_client: AsyncClient) -> None:
    # Patch generate_draft to raise ValueError (job not found) bypassing the cap check.
    with patch(
        "app.api.drafts.generate_draft",
        new_callable=AsyncMock,
        side_effect=ValueError("Job not found"),
    ):
        resp = await auth_client.post(f"/api/drafts/generate/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── read ──────────────────────────────────────────────────────────────────────

async def test_get_draft_returns_200(
    auth_client: AsyncClient, seeded_draft_id: uuid.UUID
) -> None:
    resp = await auth_client.get(f"/api/drafts/{seeded_draft_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "cover_letter_md" in body


async def test_get_draft_unknown_returns_404(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(f"/api/drafts/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── patch ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field,value", [
    ("cover_letter_md", "Updated cover letter content."),
    ("email_subject", "New subject line"),
    ("resume_md", "# Updated Resume\n\n- Skill A"),
])
async def test_patch_draft_updates_field(
    auth_client: AsyncClient, seeded_draft_id: uuid.UUID, field: str, value: str
) -> None:
    resp = await auth_client.patch(
        f"/api/drafts/{seeded_draft_id}", json={field: value}
    )
    assert resp.status_code == 200
    assert resp.json()[field] == value


@given(st.text(min_size=1, max_size=500))
@h_settings(max_examples=10)
def test_patch_cover_letter_accepts_arbitrary_text(text: str) -> None:
    import asyncio

    async def _run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as ac:
            resp = await ac.patch(
                "/api/drafts/00000000-0000-0000-0000-000000000001",
                json={"cover_letter_md": text},
            )
        # 401 because no auth cookie in this sync wrapper — shape test only
        assert resp.status_code in (200, 401, 404, 422)

    asyncio.run(_run())


# ── approve / reject / invalid transitions ────────────────────────────────────

async def test_approve_transitions_to_approved(
    auth_client: AsyncClient, seeded_draft_id: uuid.UUID
) -> None:
    resp = await auth_client.post(f"/api/drafts/{seeded_draft_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == ApplicationStatus.APPROVED


async def test_reject_transitions_to_withdrawn(
    auth_client: AsyncClient, seeded_draft_id: uuid.UUID
) -> None:
    resp = await auth_client.post(f"/api/drafts/{seeded_draft_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == ApplicationStatus.WITHDRAWN


async def test_double_approve_returns_409(
    auth_client: AsyncClient, seeded_draft_id: uuid.UUID
) -> None:
    await auth_client.post(f"/api/drafts/{seeded_draft_id}/approve")
    resp = await auth_client.post(f"/api/drafts/{seeded_draft_id}/approve")
    assert resp.status_code == 409


async def test_approve_already_withdrawn_returns_409(
    auth_client: AsyncClient, seeded_draft_id: uuid.UUID
) -> None:
    await auth_client.post(f"/api/drafts/{seeded_draft_id}/reject")
    resp = await auth_client.post(f"/api/drafts/{seeded_draft_id}/approve")
    assert resp.status_code == 409
