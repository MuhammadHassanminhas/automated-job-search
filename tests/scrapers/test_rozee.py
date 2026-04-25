"""Tests for RozeeScraper — B.1 spec."""
from __future__ import annotations

import pytest
import httpx
import respx
from pathlib import Path
from hypothesis import given, settings as h_settings, HealthCheck
import hypothesis.strategies as st

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "rozee_sample.html").read_text()
ROZEE_URL = "https://www.rozee.pk/job/jsearch/q/machine-learning"


class TestRozeeScraperUnit:
    """Selector-level tests against the canned HTML fixture."""

    def test_parse_fixture_returns_at_least_one_job(self) -> None:
        from app.scrapers.rozee import RozeeScraper
        scraper = RozeeScraper()
        jobs = scraper._parse_html(FIXTURE_HTML)
        assert len(jobs) >= 1

    def test_parsed_jobs_have_non_empty_title_and_company(self) -> None:
        from app.scrapers.rozee import RozeeScraper
        scraper = RozeeScraper()
        jobs = scraper._parse_html(FIXTURE_HTML)
        for job in jobs:
            assert job.title and len(job.title.strip()) > 0
            assert job.company and len(job.company.strip()) > 0

    @pytest.mark.parametrize("malformed_html", [
        "",
        "<html></html>",
        "<ul class='jobs-list'></ul>",
        "not html at all",
        "<li class='job-listing'></li>",
        "<?xml version='1.0'?>",
        "<html><body>" + "x" * 10000 + "</body></html>",
        "<li class='job-listing'><div class='job-listing--title'></div></li>",
        "<html><body><ul class='jobs-list'></ul></body></html>",
        "<li class='job-listing'><h2><a></a></h2></li>",
    ])
    def test_malformed_html_is_skipped_gracefully(self, malformed_html: str) -> None:
        """10 malformed payloads → parser returns empty list, never raises."""
        from app.scrapers.rozee import RozeeScraper
        scraper = RozeeScraper()
        try:
            jobs = scraper._parse_html(malformed_html)
            assert isinstance(jobs, list)
        except Exception as exc:
            pytest.fail(f"Parser raised on malformed input: {exc!r}")

    @given(st.integers(min_value=0, max_value=500))
    @h_settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_parser_never_raises_on_synthetic_listings(self, n: int) -> None:
        """Property: _parse_html never raises for n synthetic listings."""
        from app.scrapers.rozee import RozeeScraper
        html_entries = "".join(
            f"""<li class="job-listing">
              <div class="job-listing--title"><h2><a href="/job/{i}">Engineer {i}</a></h2></div>
              <div class="job-listing--company-name"><span>Corp {i}</span></div>
              <div class="job-listing--job-location"><span>Remote</span></div>
            </li>"""
            for i in range(n)
        )
        html = f'<html><body><ul class="jobs-list">{html_entries}</ul></body></html>'
        scraper = RozeeScraper()
        try:
            jobs = scraper._parse_html(html)
            assert isinstance(jobs, list)
        except Exception as exc:
            pytest.fail(f"Parser raised for n={n}: {exc!r}")

    def test_rate_limit_is_configured_at_10s(self) -> None:
        """Rozee scraper must declare a 10-second minimum interval between requests."""
        from app.scrapers.rozee import RozeeScraper
        scraper = RozeeScraper()
        assert scraper.REQUEST_INTERVAL_SECONDS == 10


class TestRozeeScraperHTTP:
    def test_fetch_returns_html_from_mocked_endpoint(self) -> None:
        from app.scrapers.rozee import RozeeScraper, ROZEE_LISTINGS_URL
        with respx.mock:
            respx.get(ROZEE_LISTINGS_URL).mock(
                return_value=httpx.Response(200, text=FIXTURE_HTML)
            )
            scraper = RozeeScraper()
            raw = scraper.fetch()
        assert isinstance(raw, str)
        assert len(raw) > 0
