from __future__ import annotations

import warnings
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from app.models.job import JobSource as JobSourceEnum
from app.scrapers._ratelimit import RateLimiter
from app.scrapers._robots import can_fetch
from app.scrapers.base import JobSource, RawJob

ROZEE_LISTINGS_URL = "https://www.rozee.pk/job/jsearch/q/machine-learning"

_UA = "internship-intel/0.1.0 (+contact)"
_limiter = RateLimiter(10.0)


class RozeeScraper(JobSource):
    REQUEST_INTERVAL_SECONDS: int = 10

    def __init__(self) -> None:
        self._last_etag: Optional[str] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch(self) -> str:
        """Fetch the listing page; honour ETag to skip unchanged content."""
        _limiter.wait()
        try:
            resp = httpx.get(
                ROZEE_LISTINGS_URL,
                headers={"User-Agent": _UA},
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except Exception:
            return ""

        new_etag: Optional[str] = resp.headers.get("ETag") or resp.headers.get("etag")

        if new_etag and new_etag == self._last_etag:
            return ""

        if new_etag:
            self._last_etag = new_etag

        html = resp.text
        self.normalize(html)
        return html

    def normalize(self, html: str) -> list[RawJob]:
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[RawJob]:
        if not html or not html.strip():
            return []
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
                soup = BeautifulSoup(html, "lxml")
        except Exception:
            return []

        jobs: list[RawJob] = []
        containers = soup.find_all("li", class_="job-listing")
        for container in containers:
            try:
                title_div = container.find("div", class_="job-listing--title")
                if not title_div:
                    continue
                h2_tag = title_div.find("h2")
                if not h2_tag:
                    continue
                link_tag = h2_tag.find("a")
                if not link_tag:
                    continue
                title = link_tag.text.strip()
                if not title:
                    continue
                href = link_tag.get("href", "")
                url = "https://www.rozee.pk" + href if href else ""
                if not url:
                    continue

                company_div = container.find("div", class_="job-listing--company-name")
                company_span = company_div.find("span") if company_div else None
                company = company_span.text.strip() if company_span else ""
                if not company:
                    continue

                loc_div = container.find("div", class_="job-listing--job-location")
                if loc_div:
                    loc_span = loc_div.find("span")
                    location = loc_span.text.strip() if loc_span else "Pakistan"
                else:
                    location = "Pakistan"

                # Derive external_id from URL path, e.g. "/job/1234" -> "1234"
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.rstrip("/").split("/") if p]
                external_id = path_parts[-1] if path_parts else href

                jobs.append(
                    RawJob(
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        description="",
                        external_id=external_id,
                        source=JobSourceEnum.ROZEE,
                        remote_allowed=(location.lower() == "remote"),
                    )
                )
            except Exception:
                continue

        return jobs

    # ------------------------------------------------------------------
    # JobSource ABC compat
    # ------------------------------------------------------------------

    def run(self) -> list[RawJob]:
        html = self.fetch()
        if not html:
            return []
        return self.normalize(html)

    can_fetch_gate = staticmethod(can_fetch)
