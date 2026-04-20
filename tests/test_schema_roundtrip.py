"""
A.1 schema round-trip tests — polyfactory factories for all 6 models,
hypothesis property test that n rows can be built and have required fields.
Fails at collection with ModuleNotFoundError('app') until app/ exists.
"""
from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings
from polyfactory.factories.base import BaseFactory

from app.models.job import Job  # ModuleNotFoundError until app/ exists
from app.models.profile import Profile
from app.models.application import Application
from app.models.draft import Draft
from app.models.outreach_event import OutreachEvent
from app.models.llm_call import LlmCall


class JobFactory(BaseFactory):
    __model__ = Job


class ProfileFactory(BaseFactory):
    __model__ = Profile


class ApplicationFactory(BaseFactory):
    __model__ = Application


class DraftFactory(BaseFactory):
    __model__ = Draft


class OutreachEventFactory(BaseFactory):
    __model__ = OutreachEvent


class LlmCallFactory(BaseFactory):
    __model__ = LlmCall


@given(st.integers(min_value=1, max_value=200))
@settings(max_examples=10)
def test_job_factory_builds_n_rows(n: int) -> None:
    jobs = JobFactory.batch(n)
    assert len(jobs) == n
    for job in jobs:
        assert job.title is not None
        assert job.source is not None


@given(st.integers(min_value=1, max_value=200))
@settings(max_examples=10)
def test_profile_factory_builds_n_rows(n: int) -> None:
    profiles = ProfileFactory.batch(n)
    assert len(profiles) == n
    for p in profiles:
        assert p.email is not None


@given(st.integers(min_value=1, max_value=200))
@settings(max_examples=10)
def test_application_factory_builds_n_rows(n: int) -> None:
    apps = ApplicationFactory.batch(n)
    assert len(apps) == n


@given(st.integers(min_value=1, max_value=200))
@settings(max_examples=10)
def test_draft_factory_builds_n_rows(n: int) -> None:
    drafts = DraftFactory.batch(n)
    assert len(drafts) == n


@given(st.integers(min_value=1, max_value=200))
@settings(max_examples=10)
def test_llm_call_factory_builds_n_rows(n: int) -> None:
    calls = LlmCallFactory.batch(n)
    assert len(calls) == n
    for c in calls:
        assert c.provider is not None
