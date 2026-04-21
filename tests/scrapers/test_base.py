"""Tests for app.scrapers.base — RawJob dataclass and JobSource ABC."""
import pytest
from datetime import datetime, timezone
from hypothesis import given, settings
import hypothesis.strategies as st

from app.scrapers.base import RawJob, JobSource


class TestJobSourceABC:
    def test_job_source_abc_cannot_instantiate(self):
        """JobSource is abstract — direct instantiation must raise TypeError."""
        with pytest.raises(TypeError):
            JobSource()

    def test_concrete_source_instantiates(self):
        """A subclass that implements all abstract methods must instantiate."""

        class ConcreteSource(JobSource):
            def fetch(self):
                return []

            def normalize(self, raw):
                return []

        src = ConcreteSource()
        assert src is not None

    def test_concrete_source_missing_normalize_raises(self):
        """Subclass missing normalize() must still raise TypeError."""

        class IncompleteSource(JobSource):
            def fetch(self):
                return []

        with pytest.raises(TypeError):
            IncompleteSource()

    def test_concrete_source_missing_fetch_raises(self):
        """Subclass missing fetch() must still raise TypeError."""

        class IncompleteSource(JobSource):
            def normalize(self, raw):
                return []

        with pytest.raises(TypeError):
            IncompleteSource()


@pytest.mark.parametrize(
    "title,company,location",
    [
        ("", "", ""),
        ("ML Engineer", "Acme Corp", "Remote"),
        ("日本語タイトル", "会社名", "東京"),
        ("A" * 500, "B" * 500, "C" * 500),
        (None, None, None),
    ],
)
def test_raw_job_holds_any_value(title, company, location):
    """RawJob must accept any value for title, company, location."""
    job = RawJob(title=title, company=company, location=location, url="https://example.com")
    assert job.title == title
    assert job.company == company
    assert job.location == location


def test_raw_job_discovered_at_defaults_to_utc_now():
    """RawJob.discovered_at must default to UTC datetime."""
    before = datetime.now(timezone.utc)
    job = RawJob(title="X", company="Y", location="Z", url="https://example.com")
    after = datetime.now(timezone.utc)
    assert job.discovered_at >= before
    assert job.discovered_at <= after
    assert job.discovered_at.tzinfo is not None


def test_raw_job_explicit_discovered_at():
    """RawJob.discovered_at can be set explicitly."""
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    job = RawJob(title="X", company="Y", location="Z", url="https://example.com", discovered_at=ts)
    assert job.discovered_at == ts


@given(st.text(), st.text())
@settings(max_examples=100)
def test_raw_job_never_raises_on_arbitrary_title_company(title, company):
    """Property: RawJob construction never raises for any title/company strings."""
    job = RawJob(title=title, company=company, location="Remote", url="https://example.com")
    assert job.title == title
    assert job.company == company
