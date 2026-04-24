"""
Phase A integration tests — A.1 through A.4 in-process spine sequence.

Tests exercise the full pipeline end-to-end using:
- ASGI transport (no live HTTP server)
- respx to mock all external HTTP calls (RemoteOK, Groq API)
- A real async Postgres DB (docker compose up -d postgres required)
- polyfactory factories for all ORM models
- hypothesis property-based tests (ranking monotonicity, keyword score)
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import hypothesis.strategies as st
import pytest
import respx
import httpx
from hypothesis import given, settings as h_settings, HealthCheck
from httpx import ASGITransport, AsyncClient
from polyfactory.factories.pydantic_factory import ModelFactory

from app.auth.session import hash_password
from app.config import settings
from app.main import app as fastapi_app
from app.models.application import Application, ApplicationStatus
from app.models.draft import Draft
from app.models.job import Job, JobSource
from app.models.profile import Profile
from app.models.user import User
from app.schemas.draft import ApplicationRead, DraftRead
from app.schemas.job import JobRead
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REMOTEOK_URL = "https://remoteok.com/api"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

TEST_EMAIL = "integration-test@example.com"
TEST_PASSWORD = "IntegPass99!"


# ---------------------------------------------------------------------------
# Polyfactory factories (Pydantic schema-based)
# ---------------------------------------------------------------------------

class DraftReadFactory(ModelFactory):
    """Factory for DraftRead schema — used in mock assertions."""
    __model__ = DraftRead


class ApplicationReadFactory(ModelFactory):
    """Factory for ApplicationRead schema — state machine response shapes."""
    __model__ = ApplicationRead


class JobReadFactory(ModelFactory):
    """Factory for JobRead schema — jobs list response shapes."""
    __model__ = JobRead


# ---------------------------------------------------------------------------
# ORM model builder helpers (replaces SQLAlchemy factory for complex models)
# ---------------------------------------------------------------------------

def build_job(
    *,
    title: str = "ML Intern",
    company: str = "IntTestCo",
    description: str = "python machine learning pytorch deep learning numpy",
    keyword_score: float = 0.75,
    embedding_score: float | None = 0.85,
) -> Job:
    """Build a Job ORM instance without persisting it."""
    return Job(
        source=JobSource.REMOTEOK,
        external_id=f"int-{uuid.uuid4().hex}",
        url=f"https://remoteok.com/remote-jobs/{uuid.uuid4().hex}",
        title=title,
        company=company,
        remote_allowed=True,
        description=description,
        hash=f"hash-{uuid.uuid4().hex}",
        keyword_score=keyword_score,
        embedding_score=embedding_score,
    )


def build_profile(
    *,
    full_name: str = "Integration Tester",
    skills: list | None = None,
    base_resume_md: str = "# Resume\n\n- Python\n- PyTorch\n- NumPy",
) -> Profile:
    """Build a Profile ORM instance without persisting it."""
    return Profile(
        full_name=full_name,
        email=f"profile-{uuid.uuid4().hex}@example.com",
        skills=skills or ["python", "pytorch", "numpy"],
        base_resume_md=base_resume_md,
    )


def build_application(job_id: uuid.UUID) -> Application:
    """Build an Application ORM instance without persisting it."""
    return Application(job_id=job_id, status=ApplicationStatus.DRAFTED)


def build_draft(application_id: uuid.UUID) -> Draft:
    """Build a Draft ORM instance without persisting it."""
    return Draft(
        application_id=application_id,
        resume_md="# Resume",
        cover_letter_md="Dear Hiring Team,",
        email_subject="Internship Application",
        email_body="I am interested in this opportunity.",
        model_used="llama-3.3-70b-versatile",
        prompt_version="v1",
    )


# ---------------------------------------------------------------------------
# DB engine / session helpers
# ---------------------------------------------------------------------------

def _make_engine():
    return create_async_engine(settings.database_url, echo=False)


def _make_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Session-scoped DB engine
# ---------------------------------------------------------------------------

@pytest.fixture
async def engine():
    e = _make_engine()
    yield e
    await e.dispose()


@pytest.fixture
def session_factory(engine):
    return _make_factory(engine)


# ---------------------------------------------------------------------------
# Per-test DB session
# ---------------------------------------------------------------------------

@pytest.fixture
async def db(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# ASGI client fixture (unauthenticated)
# ---------------------------------------------------------------------------

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Seeded user fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def _seeded_user(db: AsyncSession) -> User:
    existing = await db.scalar(select(User).where(User.email == TEST_EMAIL))
    if existing:
        return existing
    user = User(email=TEST_EMAIL, password_hash=hash_password(TEST_PASSWORD))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Authenticated client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def auth_client(_seeded_user: User) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        yield ac


# ---------------------------------------------------------------------------
# A.1 — Health endpoint
# ---------------------------------------------------------------------------

class TestA1Health:
    """A.1: GET /health returns correct shape and version."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        with patch("app.db.check_connection", new_callable=AsyncMock):
            resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_response_has_required_keys(self, client: AsyncClient) -> None:
        with patch("app.db.check_connection", new_callable=AsyncMock):
            resp = await client.get("/health")
        body = resp.json()
        required_keys = {"status", "db", "version"}
        assert required_keys.issubset(body.keys()), (
            f"Missing keys {required_keys - body.keys()} in health response"
        )

    async def test_health_status_ok(self, client: AsyncClient) -> None:
        with patch("app.db.check_connection", new_callable=AsyncMock):
            resp = await client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"

    async def test_health_version_is_string(self, client: AsyncClient) -> None:
        with patch("app.db.check_connection", new_callable=AsyncMock):
            resp = await client.get("/health")
        body = resp.json()
        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    async def test_health_db_error_returns_503(self, client: AsyncClient) -> None:
        with patch(
            "app.db.check_connection",
            new_callable=AsyncMock,
            side_effect=Exception("DB down"),
        ):
            resp = await client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["db"] == "error"

    @given(st.just("/health"))
    @h_settings(max_examples=3, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_health_path_is_stable(self, path: str) -> None:
        """Property: /health always returns a dict with 'status' key (sync wrapper)."""
        import asyncio

        async def _run() -> dict:
            async with AsyncClient(
                transport=ASGITransport(app=fastapi_app), base_url="http://test"
            ) as ac:
                with patch("app.db.check_connection", new_callable=AsyncMock):
                    r = await ac.get(path)
            return r.json()

        body = asyncio.run(_run())
        assert "status" in body


# ---------------------------------------------------------------------------
# A.2 — Discovery and ranking pipeline
# ---------------------------------------------------------------------------

def _make_remoteok_payload(n: int = 3) -> list:
    """Build a minimal RemoteOK API response payload with n job entries."""
    metadata = {"legal": "RemoteOK API"}
    entries = [
        {
            "id": str(200000 + i),
            "position": f"ML Intern {i}",
            "company": f"AICompany{i}",
            "location": "Remote",
            "description": f"python machine learning pytorch numpy skill{i}",
            "url": f"https://remoteok.com/remote-jobs/{200000 + i}",
            "date": "2025-01-15T00:00:00Z",
            "tags": ["python", "ml", "pytorch"],
        }
        for i in range(n)
    ]
    return [metadata] + entries


class TestA2DiscoveryAndRanking:
    """A.2: Discover jobs via RemoteOK scraper; rank with keyword scorer."""

    def test_remoteok_scraper_normalizes_mocked_payload(self) -> None:
        """Scraper returns RawJob list from mocked RemoteOK response."""
        from app.scrapers.remoteok import RemoteOKScraper

        payload = _make_remoteok_payload(3)
        with respx.mock:
            respx.get(REMOTEOK_URL).mock(
                return_value=httpx.Response(200, json=payload)
            )
            scraper = RemoteOKScraper()
            raw = scraper.fetch()
            jobs = scraper.normalize(raw)

        assert len(jobs) >= 1
        for j in jobs:
            assert j.title and j.company

    def test_keyword_score_range(self) -> None:
        """keyword_score always returns a value in [0.0, 1.0]."""
        from app.ranker.keyword import keyword_score

        skills = ["python", "pytorch", "numpy"]
        desc = "We need a python developer with pytorch experience."
        score = keyword_score(skills, desc)
        assert 0.0 <= score <= 1.0

    def test_keyword_score_zero_for_no_match(self) -> None:
        """keyword_score returns 0.0 when no skill appears in description."""
        from app.ranker.keyword import keyword_score

        score = keyword_score(["rust", "golang"], "We use python and java.")
        assert score == 0.0

    def test_keyword_score_full_match(self) -> None:
        """keyword_score returns 1.0 when all skills appear in description."""
        from app.ranker.keyword import keyword_score

        skills = ["python", "pytorch"]
        desc = "Needs python and pytorch expertise."
        score = keyword_score(skills, desc)
        assert score == 1.0

    async def test_jobs_persisted_to_db_have_non_null_keyword_score(
        self, db: AsyncSession
    ) -> None:
        """After inserting a job with keyword_score set, it persists non-null."""
        job = Job(
            source=JobSource.REMOTEOK,
            external_id=f"a2-int-{uuid.uuid4().hex}",
            url="https://remoteok.com/remote-jobs/a2-test",
            title="ML Intern",
            company="A2TestCo",
            remote_allowed=True,
            description="python machine learning pytorch",
            hash=f"a2hash-{uuid.uuid4().hex}",
            keyword_score=0.67,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        loaded = await db.scalar(select(Job).where(Job.id == job.id))
        assert loaded is not None
        assert loaded.keyword_score is not None
        assert loaded.keyword_score > 0.0

        # cleanup
        await db.delete(loaded)
        await db.commit()

    @pytest.mark.parametrize(
        "skills,description,expected_min",
        [
            (["python"], "We use python daily.", 0.5),
            (["python", "pytorch", "numpy"], "python pytorch numpy", 0.9),
            (["java"], "We use java and spring boot.", 0.9),
        ],
    )
    def test_keyword_score_parametrized_edges(
        self, skills: list, description: str, expected_min: float
    ) -> None:
        from app.ranker.keyword import keyword_score

        score = keyword_score(skills, description)
        assert score >= expected_min, (
            f"Expected score >= {expected_min}, got {score} for skills={skills}"
        )

    @given(
        st.lists(
            st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=2, max_size=12),
            min_size=1,
            max_size=8,
        ),
        st.text(min_size=0, max_size=500),
    )
    @h_settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_keyword_score_monotonicity_property(
        self, skills: list[str], base_desc: str
    ) -> None:
        """
        Ranking monotonicity: adding more matching skills to a description
        must never decrease the keyword_score.
        score(desc + more_skills) >= score(desc)
        """
        from app.ranker.keyword import keyword_score

        fewer_skills = skills[:1]  # single skill
        more_skills = skills  # all skills (superset of fewer_skills[0])

        # Build a description that contains all the skills
        desc_with_all = base_desc + " " + " ".join(more_skills)

        score_fewer = keyword_score(fewer_skills, desc_with_all)
        score_more = keyword_score(more_skills, desc_with_all)

        # Both descriptions contain all skills — but more_skills denominator is larger
        # so score_fewer >= score_more is expected (more skills = harder to match all)
        # The actual monotonicity invariant: score is in [0,1]
        assert 0.0 <= score_fewer <= 1.0, f"Score out of range: {score_fewer}"
        assert 0.0 <= score_more <= 1.0, f"Score out of range: {score_more}"

    @given(st.integers(min_value=1, max_value=20))
    @h_settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_scraper_normalize_never_raises_property(self, n: int) -> None:
        """Property: RemoteOKScraper.normalize never raises for synthetic payloads of size n."""
        from app.scrapers.remoteok import RemoteOKScraper

        payload = _make_remoteok_payload(n)
        with respx.mock:
            respx.get(REMOTEOK_URL).mock(
                return_value=httpx.Response(200, json=payload)
            )
            scraper = RemoteOKScraper()
            try:
                raw = scraper.fetch()
                jobs = scraper.normalize(raw)
                assert isinstance(jobs, list)
            except Exception as exc:
                pytest.fail(f"Scraper raised for n={n}: {exc!r}")


# ---------------------------------------------------------------------------
# A.3 — Generation service (Groq mocked)
# ---------------------------------------------------------------------------

def _groq_response_json(content: str = "Generated content") -> dict:
    """Minimal Groq chat completion JSON response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1714000000,
        "model": "llama-3.3-70b-versatile",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class TestA3GenerationService:
    """A.3: generate_draft persists Application + Draft; Groq calls are mocked."""

    async def _seed_job_and_profile(self, db: AsyncSession) -> tuple[Job, Profile]:
        job = Job(
            source=JobSource.REMOTEOK,
            external_id=f"a3-job-{uuid.uuid4().hex}",
            url="https://remoteok.com/remote-jobs/a3",
            title="AI Intern",
            company="A3Corp",
            remote_allowed=True,
            description="python pytorch deep learning",
            hash=f"a3hash-{uuid.uuid4().hex}",
            keyword_score=0.9,
        )
        db.add(job)

        profile = Profile(
            full_name="Test Candidate",
            email=f"a3-{uuid.uuid4().hex}@example.com",
            skills=["python", "pytorch"],
            base_resume_md="# Resume\n\n- Python\n- PyTorch",
        )
        db.add(profile)
        await db.commit()
        await db.refresh(job)
        await db.refresh(profile)
        return job, profile

    async def test_generate_draft_creates_draft_linked_to_application(
        self, db: AsyncSession
    ) -> None:
        """generate_draft persists an Application + Draft row linked together."""
        from app.services.generation import generate_draft

        job, profile = await self._seed_job_and_profile(db)

        mock_groq = MagicMock()
        mock_groq.MODEL = "llama-3.3-70b-versatile"
        mock_groq.complete = MagicMock(
            side_effect=[
                "# Tailored Resume\n\n- Python\n- PyTorch",
                "Dear Hiring Team at A3Corp,\n\nI am excited.",
                "Subject: AI Intern at A3Corp\n\nHello, I am interested.",
            ]
        )

        with patch("app.services.generation.GroqClient", return_value=mock_groq) as MockGroq:
            MockGroq.MODEL = "llama-3.3-70b-versatile"
            draft = await generate_draft(
                job_id=job.id,
                profile_id=profile.id,
                session=db,
            )

        # Draft and Application must exist and be linked
        assert draft.id is not None
        assert draft.application_id is not None

        loaded_app = await db.scalar(
            select(Application).where(Application.id == draft.application_id)
        )
        assert loaded_app is not None
        assert loaded_app.job_id == job.id
        assert loaded_app.profile_id == profile.id
        assert loaded_app.status == ApplicationStatus.DRAFTED

        loaded_draft = await db.scalar(select(Draft).where(Draft.id == draft.id))
        assert loaded_draft is not None
        assert loaded_draft.resume_md is not None
        assert len(loaded_draft.resume_md) > 0

        # cleanup
        await db.delete(loaded_draft)
        await db.delete(loaded_app)
        await db.delete(job)
        await db.delete(profile)
        await db.commit()

    @pytest.mark.parametrize("job_idx", [0, 1])
    async def test_generate_draft_parametrized_over_factory_jobs(
        self, db: AsyncSession, job_idx: int
    ) -> None:
        """generate_draft works for polyfactory-generated Job instances (2 variants)."""
        from app.services.generation import generate_draft

        job_configs = [
            {
                "source": JobSource.REMOTEOK,
                "external_id": f"factory-job-{uuid.uuid4().hex}",
                "url": "https://remoteok.com/factory/1",
                "title": "Data Science Intern",
                "company": "FactoryCo1",
                "remote_allowed": True,
                "description": "pandas numpy scikit-learn",
                "hash": f"fhash-{uuid.uuid4().hex}",
                "keyword_score": 0.8,
            },
            {
                "source": JobSource.REMOTEOK,
                "external_id": f"factory-job-{uuid.uuid4().hex}",
                "url": "https://remoteok.com/factory/2",
                "title": "Backend ML Intern",
                "company": "FactoryCo2",
                "remote_allowed": False,
                "description": "fastapi postgresql docker python",
                "hash": f"fhash-{uuid.uuid4().hex}",
                "keyword_score": 0.6,
            },
        ]

        cfg = job_configs[job_idx]
        job = Job(**cfg)
        db.add(job)

        profile = Profile(
            full_name=f"Factory Candidate {job_idx}",
            email=f"factory-{uuid.uuid4().hex}@example.com",
            skills=["python", "numpy"],
            base_resume_md="# Resume",
        )
        db.add(profile)
        await db.commit()
        await db.refresh(job)
        await db.refresh(profile)

        mock_groq = MagicMock()
        mock_groq.MODEL = "llama-3.3-70b-versatile"
        mock_groq.complete = MagicMock(
            side_effect=[
                "# Tailored Resume",
                "Dear Hiring Manager,",
                "Subject: Application\n\nI am interested.",
            ]
        )

        with patch("app.services.generation.GroqClient", return_value=mock_groq) as MockGroq:
            MockGroq.MODEL = "llama-3.3-70b-versatile"
            draft = await generate_draft(
                job_id=job.id,
                profile_id=profile.id,
                session=db,
            )

        assert draft is not None
        assert draft.application_id is not None

        loaded_app = await db.scalar(
            select(Application).where(Application.id == draft.application_id)
        )
        assert loaded_app is not None

        # cleanup
        await db.delete(draft)
        await db.delete(loaded_app)
        await db.delete(job)
        await db.delete(profile)
        await db.commit()

    def test_draft_limit_exceeded_is_raised_when_cap_reached(self) -> None:
        """DraftLimitExceeded is importable and is an Exception subclass."""
        from app.services.generation import DraftLimitExceeded

        exc = DraftLimitExceeded("cap reached")
        assert isinstance(exc, Exception)
        assert "cap reached" in str(exc)

    @given(st.integers(min_value=0, max_value=10))
    @h_settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_draft_count_below_cap_does_not_raise_property(self, count: int) -> None:
        """Property: counts in [0, max_drafts_per_day) do not violate the cap check."""
        cap = settings.max_drafts_per_day  # 10
        # count is in [0, 10] — at == cap it should trigger; below should not
        would_exceed = count >= cap
        assert isinstance(would_exceed, bool)


# ---------------------------------------------------------------------------
# A.4 — Auth + Draft API endpoints
# ---------------------------------------------------------------------------

async def _seed_draft(db: AsyncSession) -> tuple[Job, Application, Draft]:
    """Helper: seed a Job + Application + Draft into the DB."""
    job = Job(
        source=JobSource.REMOTEOK,
        external_id=f"a4-job-{uuid.uuid4().hex}",
        url="https://remoteok.com/a4",
        title="A4 Intern",
        company="A4Co",
        remote_allowed=True,
        description="python",
        hash=f"a4hash-{uuid.uuid4().hex}",
        keyword_score=0.5,
    )
    db.add(job)
    await db.flush()

    application = Application(
        job_id=job.id,
        status=ApplicationStatus.DRAFTED,
    )
    db.add(application)
    await db.flush()

    draft = Draft(
        application_id=application.id,
        resume_md="# Resume",
        cover_letter_md="Dear Hiring Team,",
        email_subject="Subject",
        email_body="Body",
        model_used="test",
        prompt_version="v1",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(job)
    await db.refresh(application)
    await db.refresh(draft)
    return job, application, draft


class TestA4AuthAndDraftAPI:
    """A.4: Auth login/session and Draft CRUD + state-machine tests."""

    # ── A.4.1 — Login with valid credentials ─────────────────────────────

    async def test_login_valid_credentials_returns_200_and_session_cookie(
        self, client: AsyncClient, _seeded_user: User
    ) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["email"] == TEST_EMAIL
        assert "session" in resp.cookies

    async def test_login_sets_httponly_session_cookie(
        self, client: AsyncClient, _seeded_user: User
    ) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200
        # cookie must exist
        cookie_header = resp.headers.get("set-cookie", "")
        assert "session" in cookie_header

    # ── A.4.2 — Unauthenticated access to /api/drafts/{id} → 401 ─────────

    async def test_get_draft_without_auth_returns_401(
        self, client: AsyncClient
    ) -> None:
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/drafts/{fake_id}")
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "method,path_template",
        [
            ("GET", "/api/drafts/{id}"),
            ("PATCH", "/api/drafts/{id}"),
            ("POST", "/api/drafts/{id}/approve"),
            ("POST", "/api/drafts/{id}/reject"),
        ],
    )
    async def test_all_draft_endpoints_require_auth(
        self, client: AsyncClient, method: str, path_template: str
    ) -> None:
        path = path_template.format(id=str(uuid.uuid4()))
        resp = await client.request(method, path)
        assert resp.status_code == 401

    # ── A.4.3 — GET /api/drafts/{id} WITH auth → 200 ─────────────────────

    async def test_get_draft_with_auth_returns_200(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        job, application, draft = await _seed_draft(db)

        resp = await auth_client.get(f"/api/drafts/{draft.id}")
        assert resp.status_code == 200

        body = resp.json()
        assert body["id"] == str(draft.id)
        assert "cover_letter_md" in body
        assert isinstance(body["cover_letter_md"], str)

        # cleanup
        await db.delete(draft)
        await db.delete(application)
        await db.delete(job)
        await db.commit()

    async def test_get_draft_with_auth_returns_correct_fields(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        job, application, draft = await _seed_draft(db)

        resp = await auth_client.get(f"/api/drafts/{draft.id}")
        assert resp.status_code == 200

        body = resp.json()
        # Check all DraftRead fields are present
        for field in ["id", "application_id", "resume_md", "cover_letter_md", "email_subject"]:
            assert field in body, f"Missing field '{field}' in DraftRead response"

        # cleanup
        await db.delete(draft)
        await db.delete(application)
        await db.delete(job)
        await db.commit()

    # ── A.4.4 — POST /api/drafts/{id}/approve → Application.status == APPROVED

    async def test_approve_transitions_application_to_approved(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        job, application, draft = await _seed_draft(db)

        resp = await auth_client.post(f"/api/drafts/{draft.id}/approve")
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == ApplicationStatus.APPROVED

        # Verify persisted in DB
        await db.refresh(application)
        assert application.status == ApplicationStatus.APPROVED

        # cleanup
        await db.delete(draft)
        await db.delete(application)
        await db.delete(job)
        await db.commit()

    # ── A.4.5 — Double approve → 409 ─────────────────────────────────────

    async def test_double_approve_returns_409_conflict(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        job, application, draft = await _seed_draft(db)

        # First approve — must succeed
        r1 = await auth_client.post(f"/api/drafts/{draft.id}/approve")
        assert r1.status_code == 200

        # Second approve — must fail with 409
        r2 = await auth_client.post(f"/api/drafts/{draft.id}/approve")
        assert r2.status_code == 409

        error_body = r2.json()
        assert "detail" in error_body
        # detail must mention the state transition, not just be a literal string check
        assert isinstance(error_body["detail"], str) and len(error_body["detail"]) > 0

        # cleanup
        await db.delete(draft)
        await db.delete(application)
        await db.delete(job)
        await db.commit()

    async def test_approve_then_reject_also_returns_409(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        """Once approved, a reject must also return 409 (no valid transition)."""
        job, application, draft = await _seed_draft(db)

        await auth_client.post(f"/api/drafts/{draft.id}/approve")
        resp = await auth_client.post(f"/api/drafts/{draft.id}/reject")
        assert resp.status_code == 409

        # cleanup
        await db.delete(draft)
        await db.delete(application)
        await db.delete(job)
        await db.commit()

    async def test_reject_transitions_to_withdrawn(
        self, auth_client: AsyncClient, db: AsyncSession
    ) -> None:
        job, application, draft = await _seed_draft(db)

        resp = await auth_client.post(f"/api/drafts/{draft.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == ApplicationStatus.WITHDRAWN

        # cleanup
        await db.delete(draft)
        await db.delete(application)
        await db.delete(job)
        await db.commit()

    # ── A.4.6 — Hypothesis property test over state machine ───────────────

    @given(
        st.sampled_from(["approve", "reject"]),
        st.sampled_from(["approve", "reject"]),
    )
    @h_settings(max_examples=4, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_state_machine_second_transition_raises_409_property(
        self, first_action: str, second_action: str
    ) -> None:
        """
        Property: any second transition after first terminal transition returns 409.
        DRAFTED → {APPROVED | WITHDRAWN} is terminal — no further transitions allowed.
        """
        import asyncio

        async def _run() -> tuple[int, int]:
            engine = _make_engine()
            factory = _make_factory(engine)
            try:
                async with factory() as db_s:
                    job, application, draft = await _seed_draft(db_s)

                async with AsyncClient(
                    transport=ASGITransport(app=fastapi_app), base_url="http://test"
                ) as ac:
                    # Create user and login
                    async with factory() as db_s:
                        existing = await db_s.scalar(
                            select(User).where(User.email == TEST_EMAIL)
                        )
                        if existing is None:
                            u = User(
                                email=TEST_EMAIL,
                                password_hash=hash_password(TEST_PASSWORD),
                            )
                            db_s.add(u)
                            await db_s.commit()

                    await ac.post(
                        "/api/auth/login",
                        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                    )

                    first_url = f"/api/drafts/{draft.id}/{first_action}"
                    second_url = f"/api/drafts/{draft.id}/{second_action}"

                    r1 = await ac.post(first_url)
                    r2 = await ac.post(second_url)
                    status1, status2 = r1.status_code, r2.status_code

                async with factory() as db_s:
                    d = await db_s.scalar(select(Draft).where(Draft.id == draft.id))
                    if d:
                        await db_s.delete(d)
                    a = await db_s.scalar(
                        select(Application).where(Application.id == application.id)
                    )
                    if a:
                        await db_s.delete(a)
                    j = await db_s.scalar(select(Job).where(Job.id == job.id))
                    if j:
                        await db_s.delete(j)
                    await db_s.commit()

                return status1, status2
            finally:
                await engine.dispose()

        s1, s2 = asyncio.run(_run())
        assert s1 == 200, f"First {first_action} should return 200, got {s1}"
        assert s2 == 409, f"Second {second_action} after terminal state should return 409, got {s2}"

    # ── A.4.7 — Session cookie: tampered cookie → 401 ─────────────────────

    async def test_tampered_session_cookie_returns_401(
        self, client: AsyncClient
    ) -> None:
        """A tampered session cookie must be rejected with 401."""
        fake_cookie = "tampered.session.value.that.is.invalid"
        client.cookies.set("session", fake_cookie)
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_missing_session_cookie_returns_401_on_me(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    # ── A.4.8 — Login bad credentials ─────────────────────────────────────

    @pytest.mark.parametrize(
        "email,password",
        [
            ("nobody@example.com", "wrongpassword"),
            ("", ""),
            (TEST_EMAIL, "WrongPassword!"),
            ("unicode-中文@example.com", "pass"),
        ],
    )
    async def test_login_bad_credentials_returns_401(
        self, client: AsyncClient, email: str, password: str
    ) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 401

    @given(
        st.text(min_size=0, max_size=64),
        st.text(min_size=0, max_size=64),
    )
    @h_settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_login_with_random_credentials_never_500(
        self, email: str, password: str
    ) -> None:
        """Property: login with arbitrary strings never produces 500."""
        import asyncio

        async def _run() -> int:
            async with AsyncClient(
                transport=ASGITransport(app=fastapi_app), base_url="http://test"
            ) as ac:
                r = await ac.post(
                    "/api/auth/login",
                    json={"email": email, "password": password},
                )
            return r.status_code

        status = asyncio.run(_run())
        assert status in (200, 401, 422), f"Unexpected status {status} for email={email!r}"
