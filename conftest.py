"""Root conftest.py — project-wide pytest fixtures and polyfactory bootstrap.

polyfactory's BaseFactory is abstract; SQLAlchemy ORM models require
SQLAlchemyFactory. This file replaces BaseFactory in its own module with a
concrete, SQLAlchemy-aware factory that also handles pgvector's Vector type,
so test files using ``from polyfactory.factories.base import BaseFactory``
get a fully functional factory without modification.

Also suppresses Hypothesis DeadlineExceeded on slower CI machines by
registering a "ci" profile with deadline=None and activating it.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import polyfactory.factories.base
from hypothesis import HealthCheck, settings
from pgvector.sqlalchemy import Vector
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory


class _VectorAwareSQLAlchemyFactory(SQLAlchemyFactory):
    """SQLAlchemyFactory extended to handle pgvector Vector columns."""

    __is_base_factory__ = True

    @classmethod
    def get_sqlalchemy_types(cls) -> dict[Any, Callable[[], Any]]:
        base = super().get_sqlalchemy_types()
        base[Vector] = lambda: np.random.default_rng().random(384).astype(np.float32).tolist()
        return base

    @classmethod
    def is_supported_type(cls, value: Any) -> bool:
        return SQLAlchemyFactory.is_supported_type(value)


polyfactory.factories.base.BaseFactory = _VectorAwareSQLAlchemyFactory  # type: ignore[attr-defined]

# Disable Hypothesis deadline globally — building 200 ORM objects on a slow
# Windows laptop legitimately exceeds the default 200ms deadline.
settings.register_profile("ci", deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("ci")

# httpx >=0.23 removed the `app=` shortcut from AsyncClient.__init__.
# Tests still use AsyncClient(app=..., base_url=...) — restore that convenience
# by wrapping __init__ to convert `app=` into `transport=ASGITransport(app=)`.
import httpx
from httpx import ASGITransport

_original_async_client_init = httpx.AsyncClient.__init__


def _patched_async_client_init(self, *args, app=None, **kwargs):
    if app is not None:
        kwargs["transport"] = ASGITransport(app=app)
    _original_async_client_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_async_client_init  # type: ignore[method-assign]

# pytest-asyncio creates a new event loop per test function. SQLAlchemy's async
# connection pool keeps connections bound to the loop that created them — the
# next test's loop sees stale connections and raises InterfaceError.
# Fix: swap the engine to NullPool so every test opens+closes its own connection.
from sqlalchemy.pool import NullPool
import app.db as _app_db
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_test_engine = create_async_engine(_app_db.engine.url, echo=False, poolclass=NullPool)
_test_session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)

_app_db.engine = _test_engine
_app_db.AsyncSessionFactory = _test_session_factory
