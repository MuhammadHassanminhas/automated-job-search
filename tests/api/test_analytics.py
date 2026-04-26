"""B.3 failing tests — analytics API endpoints and SQL views.

Tests verify:
- GET /api/analytics/source-rates returns 200 with correct schema.
- GET /api/analytics/prompt-rates returns 200 with correct schema.
- SQL views v_response_rate_by_source and v_response_rate_by_prompt_version exist.
- Property and parametrize edge cases: empty list, null prompt_version, unicode
  source name, max-length source name.

RED triggers:
- SQL views v_response_rate_by_source / v_response_rate_by_prompt_version do NOT
  exist yet → tests against live DB fail with ProgrammingError / UndefinedTable.
- The view-existence assertions in test_views_exist will fail.
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from app.api.analytics import SourceRate, PromptRate


# ---------------------------------------------------------------------------
# polyfactory factories
# ---------------------------------------------------------------------------


class SourceRateModel(BaseModel):
    source: str
    sent_count: int
    responded_count: int
    response_rate: float | None = None


class PromptRateModel(BaseModel):
    prompt_version: str | None = None
    sent_count: int
    responded_count: int
    response_rate: float | None = None


class SourceRateFactory(ModelFactory):
    __model__ = SourceRateModel

    source = lambda: f"SOURCE_{uuid.uuid4().hex[:6].upper()}"  # noqa: E731
    sent_count = lambda: 10  # noqa: E731
    responded_count = lambda: 3  # noqa: E731
    response_rate = lambda: 0.3  # noqa: E731


class PromptRateFactory(ModelFactory):
    __model__ = PromptRateModel

    prompt_version = lambda: f"v{uuid.uuid4().hex[:4]}"  # noqa: E731
    sent_count = lambda: 5  # noqa: E731
    responded_count = lambda: 2  # noqa: E731
    response_rate = lambda: 0.4  # noqa: E731


# ---------------------------------------------------------------------------
# Helper: row mock
# ---------------------------------------------------------------------------


def _make_row(data: dict) -> MagicMock:
    """Build a mock row object with attribute access matching column names."""
    row = MagicMock()
    for k, v in data.items():
        setattr(row, k, v)
    return row


def _make_db_returning_rows(rows: list) -> MagicMock:
    """Mock DB session whose execute().fetchall() returns *rows*."""
    result_mock = MagicMock()
    result_mock.fetchall = MagicMock(return_value=rows)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result_mock)
    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_rows() -> list:
    return [
        _make_row(
            {"source": "REMOTEOK", "sent_count": 10, "responded_count": 3, "response_rate": 0.3}
        ),
        _make_row(
            {"source": "INTERNSHALA", "sent_count": 5, "responded_count": 1, "response_rate": 0.2}
        ),
    ]


@pytest.fixture
def prompt_rows() -> list:
    return [
        _make_row(
            {
                "prompt_version": "v1",
                "sent_count": 8,
                "responded_count": 4,
                "response_rate": 0.5,
            }
        ),
        _make_row(
            {
                "prompt_version": None,
                "sent_count": 3,
                "responded_count": 0,
                "response_rate": None,
            }
        ),
    ]


@pytest.fixture
def analytics_client(source_rows, prompt_rows):
    """TestClient with DB mocked to return synthetic analytics rows."""
    from app.main import app as fastapi_app
    from app.db import get_db

    # Alternate which rows to return based on query text
    call_count = {"n": 0}
    all_rows = [source_rows, prompt_rows]

    async def _fake_db() -> AsyncGenerator[Any, None]:
        idx = call_count["n"] % 2
        call_count["n"] += 1
        yield _make_db_returning_rows(all_rows[idx])

    fastapi_app.dependency_overrides[get_db] = _fake_db
    with TestClient(fastapi_app, raise_server_exceptions=False) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test: GET /api/analytics/source-rates
# ---------------------------------------------------------------------------


class TestSourceRates:
    """GET /api/analytics/source-rates returns 200 with a list of SourceRate items."""

    def test_source_rates_returns_200(self, analytics_client: TestClient) -> None:
        resp = analytics_client.get("/api/analytics/source-rates")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_source_rates_returns_list(self, analytics_client: TestClient) -> None:
        resp = analytics_client.get("/api/analytics/source-rates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_source_rates_item_has_required_fields(self, analytics_client: TestClient) -> None:
        resp = analytics_client.get("/api/analytics/source-rates")
        assert resp.status_code == 200
        data = resp.json()
        if data:
            item = data[0]
            SourceRate.model_validate(item)  # validates response matches declared schema
            for field in ("source", "sent_count", "responded_count", "response_rate"):
                assert field in item, f"Missing field {field!r} in source-rates item: {item}"

    def test_source_rates_sent_count_is_non_negative(self, analytics_client: TestClient) -> None:
        resp = analytics_client.get("/api/analytics/source-rates")
        assert resp.status_code == 200
        for item in resp.json():
            assert item["sent_count"] >= 0, f"sent_count must be ≥ 0, got {item['sent_count']}"

    def test_source_rates_response_rate_is_float_or_null(
        self, analytics_client: TestClient
    ) -> None:
        resp = analytics_client.get("/api/analytics/source-rates")
        assert resp.status_code == 200
        for item in resp.json():
            rr = item.get("response_rate")
            assert rr is None or isinstance(rr, (int, float)), (
                f"response_rate must be float or null, got {rr!r}"
            )

    @pytest.mark.parametrize(
        "source_name",
        [
            "",  # empty — edge case
            "巴基斯坦",  # unicode
            "A" * 64,  # max-length
            "source with spaces",  # spaces
            "source\x00with\x00nulls",  # null bytes
        ],
    )
    def test_source_rates_edge_case_source_names(
        self, source_name: str
    ) -> None:
        """Endpoint correctly handles edge-case source names in DB data."""
        from app.main import app as fastapi_app
        from app.db import get_db

        rows = [
            _make_row(
                {
                    "source": source_name,
                    "sent_count": 1,
                    "responded_count": 0,
                    "response_rate": None,
                }
            )
        ]
        db = _make_db_returning_rows(rows)

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield db

        fastapi_app.dependency_overrides[get_db] = _fake_db
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.get("/api/analytics/source-rates")
            # Should not crash with 500 for any source name from DB
            assert resp.status_code in (200, 422), (
                f"source_name={source_name!r}: unexpected status {resp.status_code}"
            )
        finally:
            fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test: GET /api/analytics/prompt-rates
# ---------------------------------------------------------------------------


class TestPromptRates:
    """GET /api/analytics/prompt-rates returns 200 with a list of PromptRate items."""

    def test_prompt_rates_returns_200(self, analytics_client: TestClient) -> None:
        # Fresh client for prompt endpoint
        from app.main import app as fastapi_app
        from app.db import get_db

        rows = [
            _make_row(
                {
                    "prompt_version": "v2",
                    "sent_count": 7,
                    "responded_count": 2,
                    "response_rate": 0.286,
                }
            )
        ]

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield _make_db_returning_rows(rows)

        fastapi_app.dependency_overrides[get_db] = _fake_db
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.get("/api/analytics/prompt-rates")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_prompt_rates_returns_list(self, analytics_client: TestClient) -> None:
        from app.main import app as fastapi_app
        from app.db import get_db

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield _make_db_returning_rows([])

        fastapi_app.dependency_overrides[get_db] = _fake_db
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.get("/api/analytics/prompt-rates")
            assert isinstance(resp.json(), list)
        finally:
            fastapi_app.dependency_overrides.clear()

    def test_prompt_rates_null_prompt_version_allowed(self) -> None:
        """null prompt_version is a valid edge case (drafts with no versioning)."""
        from app.main import app as fastapi_app
        from app.db import get_db

        rows = [
            _make_row(
                {
                    "prompt_version": None,
                    "sent_count": 3,
                    "responded_count": 0,
                    "response_rate": None,
                }
            )
        ]

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield _make_db_returning_rows(rows)

        fastapi_app.dependency_overrides[get_db] = _fake_db
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.get("/api/analytics/prompt-rates")
            assert resp.status_code == 200
            data = resp.json()
            item = data[0]
            PromptRate.model_validate(item)  # validates response matches declared schema
            assert item["prompt_version"] is None
        finally:
            fastapi_app.dependency_overrides.clear()

    @pytest.mark.parametrize(
        "prompt_version,sent,responded",
        [
            (None, 0, 0),  # null version + zero counts
            ("", 0, 0),  # empty string version
            ("v" + "x" * 30, 100, 50),  # max-length-ish version
            ("巴基斯坦-v1", 10, 5),  # unicode version string
        ],
    )
    def test_prompt_rates_edge_case_versions(
        self, prompt_version: str | None, sent: int, responded: int
    ) -> None:
        from app.main import app as fastapi_app
        from app.db import get_db

        rr = (responded / sent) if sent > 0 else None
        rows = [
            _make_row(
                {
                    "prompt_version": prompt_version,
                    "sent_count": sent,
                    "responded_count": responded,
                    "response_rate": rr,
                }
            )
        ]

        async def _fake_db() -> AsyncGenerator[Any, None]:
            yield _make_db_returning_rows(rows)

        fastapi_app.dependency_overrides[get_db] = _fake_db
        try:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                resp = client.get("/api/analytics/prompt-rates")
            assert resp.status_code in (200, 422), (
                f"Unexpected status {resp.status_code} for prompt_version={prompt_version!r}"
            )
        finally:
            fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test: SQL views must exist (RED until migration creates them)
# ---------------------------------------------------------------------------


class TestAnalyticsSQLViews:
    """The SQL views backing analytics endpoints must exist in the database."""

    @pytest.mark.asyncio
    async def test_view_v_response_rate_by_source_exists(self) -> None:
        """Query the view directly — fails with ProgrammingError if view missing."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.config import settings

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                result = await session.execute(
                    text("SELECT 1 FROM v_response_rate_by_source LIMIT 1")
                )
                # If we get here, the view exists
                assert result is not None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_view_v_response_rate_by_prompt_version_exists(self) -> None:
        """Query the view directly — fails with ProgrammingError if view missing."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.config import settings

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT 1 FROM v_response_rate_by_prompt_version LIMIT 1"
                    )
                )
                assert result is not None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_source_view_has_required_columns(self) -> None:
        """v_response_rate_by_source must expose source, sent_count, responded_count, response_rate."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.config import settings

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT source, sent_count, responded_count, response_rate"
                        " FROM v_response_rate_by_source LIMIT 0"
                    )
                )
                assert result is not None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_prompt_view_has_required_columns(self) -> None:
        """v_response_rate_by_prompt_version must expose required columns."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.config import settings

        engine = create_async_engine(settings.database_url, echo=False)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT prompt_version, sent_count, responded_count, response_rate"
                        " FROM v_response_rate_by_prompt_version LIMIT 0"
                    )
                )
                assert result is not None
        finally:
            await engine.dispose()


# ---------------------------------------------------------------------------
# Property test: hypothesis over source names
# ---------------------------------------------------------------------------


@given(
    source_names=st.lists(
        st.text(min_size=1, max_size=64),
        min_size=0,
        max_size=5,
    )
)
@h_settings(max_examples=15)
def test_source_rates_endpoint_handles_arbitrary_source_names(
    source_names: list[str],
) -> None:
    """Property: /api/analytics/source-rates handles any list of source name strings."""
    from app.main import app as fastapi_app
    from app.db import get_db

    rows = [
        _make_row(
            {
                "source": name,
                "sent_count": len(name),
                "responded_count": max(0, len(name) - 5),
                "response_rate": None if len(name) == 0 else round(0.1 * (len(name) % 10), 2),
            }
        )
        for name in source_names
    ]

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield _make_db_returning_rows(rows)

    fastapi_app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(fastapi_app, raise_server_exceptions=False) as client:
            resp = client.get("/api/analytics/source-rates")
        assert resp.status_code in (200, 422, 500), (
            f"Unexpected status {resp.status_code} for source_names={source_names!r}"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == len(source_names)
    finally:
        fastapi_app.dependency_overrides.clear()


@given(
    prompt_versions=st.lists(
        st.one_of(st.none(), st.text(min_size=1, max_size=32)),
        min_size=0,
        max_size=5,
    )
)
@h_settings(max_examples=15)
def test_prompt_rates_endpoint_handles_arbitrary_prompt_versions(
    prompt_versions: list[str | None],
) -> None:
    """Property: /api/analytics/prompt-rates handles any list of prompt_version values."""
    from app.main import app as fastapi_app
    from app.db import get_db

    rows = [
        _make_row(
            {
                "prompt_version": pv,
                "sent_count": 5,
                "responded_count": 2,
                "response_rate": 0.4,
            }
        )
        for pv in prompt_versions
    ]

    async def _fake_db() -> AsyncGenerator[Any, None]:
        yield _make_db_returning_rows(rows)

    fastapi_app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(fastapi_app, raise_server_exceptions=False) as client:
            resp = client.get("/api/analytics/prompt-rates")
        assert resp.status_code in (200, 422, 500), (
            f"Unexpected status {resp.status_code} for prompt_versions={prompt_versions!r}"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == len(prompt_versions)
    finally:
        fastapi_app.dependency_overrides.clear()
