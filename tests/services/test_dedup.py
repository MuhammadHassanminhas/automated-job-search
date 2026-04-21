"""Tests for app.services.dedup — dedup_jobs function."""
from datetime import datetime, timezone, timedelta
from hypothesis import given, settings
import hypothesis.strategies as st

from app.scrapers.base import RawJob
from app.services.dedup import dedup_jobs


def _make_job(title: str, company: str, location: str = "Remote", offset_seconds: int = 0) -> RawJob:
    """Helper to create a RawJob with a controlled discovered_at timestamp."""
    ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)
    return RawJob(
        title=title,
        company=company,
        location=location,
        url=f"https://example.com/{title}-{company}",
        discovered_at=ts,
    )


def test_dedup_collapses_exact_duplicates():
    """5 identical RawJobs must deduplicate to exactly 1."""
    jobs = [_make_job("ML Engineer", "Acme", offset_seconds=i) for i in range(5)]
    result = dedup_jobs(jobs)
    assert len(result) == 1


def test_dedup_preserves_unique():
    """3 distinct jobs must all survive deduplication."""
    jobs = [
        _make_job("ML Engineer", "Acme"),
        _make_job("Backend Developer", "CloudCo"),
        _make_job("Data Scientist", "DataFirm"),
    ]
    result = dedup_jobs(jobs)
    assert len(result) == 3


def test_dedup_case_insensitive():
    """'ML Engineer'/'Acme' and 'ml engineer'/'acme' must be treated as the same job."""
    jobs = [
        _make_job("ML Engineer", "Acme"),
        _make_job("ml engineer", "acme"),
    ]
    result = dedup_jobs(jobs)
    assert len(result) == 1


def test_dedup_earliest_discovered_at_wins():
    """When duplicates exist, the job with the earliest discovered_at must survive."""
    early_ts = datetime(2024, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
    late_ts = datetime(2024, 1, 20, 0, 0, 0, tzinfo=timezone.utc)

    early_job = RawJob(
        title="ML Engineer",
        company="Acme",
        location="Remote",
        url="https://example.com/a",
        discovered_at=early_ts,
    )
    late_job = RawJob(
        title="ML Engineer",
        company="Acme",
        location="Remote",
        url="https://example.com/b",
        discovered_at=late_ts,
    )

    # Test both orderings to ensure it's not positional
    result_a = dedup_jobs([late_job, early_job])
    assert len(result_a) == 1
    assert result_a[0].discovered_at == early_ts

    result_b = dedup_jobs([early_job, late_job])
    assert len(result_b) == 1
    assert result_b[0].discovered_at == early_ts


def test_dedup_empty_list():
    """Empty input must return empty list."""
    assert dedup_jobs([]) == []


def test_dedup_single_job():
    """Single job must pass through unchanged."""
    job = _make_job("AI Researcher", "DeepLab")
    result = dedup_jobs([job])
    assert len(result) == 1
    assert result[0].title == job.title


@given(st.integers(min_value=1, max_value=15), st.integers(min_value=1, max_value=4))
@settings(max_examples=50)
def test_dedup_property_n_unique_times_dupes(n_unique: int, dupes_each: int):
    """Property: n_unique distinct jobs each duplicated dupes_each times → len(result) == n_unique."""
    jobs = []
    for i in range(n_unique):
        for d in range(dupes_each):
            jobs.append(
                RawJob(
                    title=f"Position {i}",
                    company=f"Company {i}",
                    location="Remote",
                    url=f"https://example.com/{i}-{d}",
                    discovered_at=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=d),
                )
            )
    result = dedup_jobs(jobs)
    assert len(result) == n_unique
