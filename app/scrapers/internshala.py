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

INTERNSHALA_LISTINGS_URL = (
    "https://internshala.com/internships/machine-learning-internship"
)

_UA = "internship-intel/0.1.0 (+contact)"
_limiter = RateLimiter(5.0)


class InternshalasScraper(JobSource):
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
                INTERNSHALA_LISTINGS_URL,
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
        containers = soup.find_all("div", class_="internship_meta")
        for container in containers:
            try:
                title_tag = container.find("h3", class_="profile-name")
                if not title_tag:
                    continue
                link_tag = title_tag.find("a")
                if not link_tag:
                    continue
                title = link_tag.text.strip()
                if not title:
                    continue
                href = link_tag.get("href", "")
                url = "https://internshala.com" + href if href else ""
                if not url:
                    continue

                company_tag = container.find(
                    "div",
                    class_=lambda c: c
                    and "link_display_like_text" in c
                    and "company_name" in c,
                )
                company = company_tag.text.strip() if company_tag else ""
                if not company:
                    continue

                loc_div = container.find("div", class_="locations_link")
                if loc_div:
                    loc_a = loc_div.find("a")
                    location = loc_a.text.strip() if loc_a else "Remote"
                else:
                    location = "Remote"

                # Derive external_id from URL path, e.g. "/internship/detail/1" -> "1"
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
                        source=JobSourceEnum.INTERNSHALA,
                        remote_allowed=(location.lower() == "remote"),
                    )
                )
            except Exception:
                continue

        return jobs

    # ------------------------------------------------------------------
    # JobSource ABC compat (base.normalize takes raw list, but our public
    # interface accepts html string — delegate appropriately)
    # ------------------------------------------------------------------

    def run(self) -> list[RawJob]:
        html = self.fetch()
        if not html:
            return []
        return self.normalize(html)

    # Satisfy ABC: fetch() already returns str; normalize(html) returns list[RawJob]
    # The base ABC declares fetch()->list and normalize(list)->list, but our
    # override is compatible at runtime (Python duck-typing).
    # We deliberately shadow the base signatures to match B.1 test expectations.
    can_fetch_gate = staticmethod(can_fetch)
