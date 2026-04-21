"""Tests for app.scrapers.remoteok — RemoteOKScraper."""
import json
import pytest
import respx
import httpx
from pathlib import Path
from hypothesis import given, settings, HealthCheck
import hypothesis.strategies as st

from app.scrapers.remoteok import RemoteOKScraper

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "remoteok_200.json"
REMOTEOK_URL = "https://remoteok.com/api"


def _load_fixture() -> list:
    return json.loads(FIXTURE_PATH.read_text())


@respx.mock
def test_remoteok_parse_fixture():
    """Scraper must return at least 1 job from the fixture payload."""
    respx.get(REMOTEOK_URL).mock(
        return_value=httpx.Response(200, json=_load_fixture())
    )
    scraper = RemoteOKScraper()
    raw = scraper.fetch()
    assert len(raw) >= 1


@respx.mock
def test_remoteok_normalize_non_empty_title_company():
    """Every normalized RawJob must have non-empty title and company."""
    respx.get(REMOTEOK_URL).mock(
        return_value=httpx.Response(200, json=_load_fixture())
    )
    scraper = RemoteOKScraper()
    raw = scraper.fetch()
    jobs = scraper.normalize(raw)
    assert len(jobs) >= 1
    for job in jobs:
        assert job.title and job.title.strip(), f"Empty title: {job!r}"
        assert job.company and job.company.strip(), f"Empty company: {job!r}"


@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_remoteok_parser_never_crashes(n):
    """Property: parser must not raise for any synthetic payload of n entries."""
    metadata = {"legal": "test"}
    entries = [
        {
            "id": str(100000 + i),
            "position": f"Engineer {i}",
            "company": f"Company {i}",
            "location": "Remote",
            "description": f"Description for job {i} with python and ml skills",
            "url": f"https://remoteok.com/remote-jobs/{100000 + i}",
            "date": "2024-01-15T00:00:00Z",
            "tags": ["python"],
        }
        for i in range(n)
    ]
    payload = [metadata] + entries

    with respx.mock:
        respx.get(REMOTEOK_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        scraper = RemoteOKScraper()
        try:
            raw = scraper.fetch()
            scraper.normalize(raw)
        except Exception as exc:
            pytest.fail(f"Parser raised unexpectedly for n={n}: {exc!r}")


@pytest.mark.parametrize(
    "payload",
    [
        [],                                        # empty list
        [None],                                    # list with null
        [None, None, None],                        # multiple nulls
        [{"legal": "ok"}, None],                   # metadata + null
        [{"legal": "ok"}, {"id": None}],           # missing position/company
        [{"legal": "ok"}, {}],                     # completely empty job object
        [{"legal": "ok"}, {"position": "", "company": ""}],  # blank strings
        "not a list",                              # non-list (string)
        {"key": "value"},                          # non-list (dict)
        [{"legal": "ok"}, {"id": "x", "position": "A" * 2000, "company": "B" * 2000,
                           "location": "C", "description": "D", "url": "https://x.com",
                           "date": "invalid-date", "tags": []}],  # oversized + bad date
    ],
)
def test_remoteok_malformed_payloads_do_not_propagate(payload):
    """Malformed payloads must not cause unhandled exceptions to propagate."""
    with respx.mock:
        respx.get(REMOTEOK_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        scraper = RemoteOKScraper()
        try:
            raw = scraper.fetch()
            if isinstance(raw, list):
                scraper.normalize(raw)
        except (ValueError, KeyError, TypeError, AttributeError):
            ...
        except Exception as exc:
            pytest.fail(f"Unexpected exception type propagated: {type(exc).__name__}: {exc}")
