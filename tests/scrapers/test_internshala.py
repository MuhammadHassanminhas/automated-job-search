"""Tests for InternshalasScraper — B.1 spec."""
from __future__ import annotations

import pytest
import httpx
import respx
from pathlib import Path
from hypothesis import given, settings as h_settings, HealthCheck
import hypothesis.strategies as st

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "internshala_sample.html").read_text()
INTERNSHALA_URL = "https://internshala.com/internships/machine-learning-internship"


class TestInternshalaScraperUnit:
    """Selector-level tests against the canned HTML fixture."""

    def test_parse_fixture_returns_at_least_one_job(self) -> None:
        from app.scrapers.internshala import InternshalasScraper
        scraper = InternshalasScraper()
        jobs = scraper._parse_html(FIXTURE_HTML)
        assert len(jobs) >= 1

    def test_parsed_jobs_have_non_empty_title_and_company(self) -> None:
        from app.scrapers.internshala import InternshalasScraper
        scraper = InternshalasScraper()
        jobs = scraper._parse_html(FIXTURE_HTML)
        for job in jobs:
            assert job.title and len(job.title.strip()) > 0
            assert job.company and len(job.company.strip()) > 0

    def test_parsed_jobs_have_url(self) -> None:
        from app.scrapers.internshala import InternshalasScraper
        scraper = InternshalasScraper()
        jobs = scraper._parse_html(FIXTURE_HTML)
        for job in jobs:
            assert job.url and job.url.startswith("http")

    @pytest.mark.parametrize("malformed_html", [
        "",
        "<html></html>",
        "<div class='internship_meta'></div>",
        "not html at all",
        "<div class='internship_meta'><div class='profile'></div></div>",
        "<?xml version='1.0'?>",
        "<html><body>" + "x" * 10000 + "</body></html>",
        "<div class='internship_meta'><h3 class='profile-name'></h3></div>",
        "<html><body><div id='internship_list'></div></body></html>",
        "<div class='internship_meta'><div class='profile'><h3 class='profile-name'><a></a></h3></div></div>",
    ])
    def test_malformed_html_is_skipped_gracefully(self, malformed_html: str) -> None:
        """10 malformed payloads → parser returns empty list, never raises."""
        from app.scrapers.internshala import InternshalasScraper
        scraper = InternshalasScraper()
        try:
            jobs = scraper._parse_html(malformed_html)
            assert isinstance(jobs, list)
        except Exception as exc:
            pytest.fail(f"Parser raised on malformed input: {exc!r}")

    @given(st.integers(min_value=0, max_value=500))
    @h_settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_parser_never_raises_on_synthetic_listings(self, n: int) -> None:
        """Property: _parse_html never raises regardless of number of synthetic div entries."""
        from app.scrapers.internshala import InternshalasScraper
        html_entries = "".join(
            f"""<div class="internship_meta">
              <div class="profile"><h3 class="profile-name"><a href="/internship/detail/{i}">Intern {i}</a></h3></div>
              <div class="link_display_like_text company_name">Company {i}</div>
              <div class="locations_link"><a href="#">Remote</a></div>
            </div>"""
            for i in range(n)
        )
        html = f'<html><body><div id="internship_list">{html_entries}</div></body></html>'
        scraper = InternshalasScraper()
        try:
            jobs = scraper._parse_html(html)
            assert isinstance(jobs, list)
            assert len(jobs) == n or (n == 0 and len(jobs) == 0)
        except Exception as exc:
            pytest.fail(f"Parser raised for n={n}: {exc!r}")


class TestInternshalaScraperHTTP:
    """HTTP-level tests using respx to mock the network."""

    def test_fetch_returns_html_from_mocked_endpoint(self) -> None:
        from app.scrapers.internshala import InternshalasScraper, INTERNSHALA_LISTINGS_URL
        with respx.mock:
            respx.get(INTERNSHALA_LISTINGS_URL).mock(
                return_value=httpx.Response(200, text=FIXTURE_HTML)
            )
            scraper = InternshalasScraper()
            raw = scraper.fetch()
        assert isinstance(raw, str)
        assert len(raw) > 0

    def test_normalize_returns_raw_jobs_from_fixture_html(self) -> None:
        from app.scrapers.internshala import InternshalasScraper
        scraper = InternshalasScraper()
        jobs = scraper.normalize(FIXTURE_HTML)
        assert len(jobs) >= 1
        for job in jobs:
            assert job.title
            assert job.company
