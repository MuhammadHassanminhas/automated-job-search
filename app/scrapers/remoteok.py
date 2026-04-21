from __future__ import annotations

import httpx

from app.scrapers.base import JobSource, RawJob
from app.scrapers._ratelimit import RateLimiter
from app.scrapers._robots import can_fetch  # noqa: F401 — used for robots gate

UA = "internship-intel/0.1.0 (+contact)"
URL = "https://remoteok.com/api"
_limiter = RateLimiter(5.0)


class RemoteOKScraper(JobSource):
    def fetch(self) -> list[dict]:
        _limiter.wait()
        try:
            resp = httpx.get(URL, headers={"User-Agent": UA}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def normalize(self, raw: list) -> list[RawJob]:
        if not isinstance(raw, list):
            return []
        jobs = []
        for entry in raw[1:]:  # skip first element (metadata)
            if not isinstance(entry, dict):
                continue
            ext_id = str(entry.get("id", "")) if entry.get("id") is not None else ""
            title = entry.get("position") or ""
            company = entry.get("company") or ""
            if not ext_id or not title:
                continue
            jobs.append(
                RawJob(
                    title=title,
                    company=company,
                    location=entry.get("location") or "Remote",
                    url=entry.get("url") or f"https://remoteok.com/remote-jobs/{ext_id}",
                    description=entry.get("description") or " ".join(entry.get("tags") or []),
                    external_id=ext_id,
                    source="remoteok",
                    posted_at=None,
                    remote_allowed=True,
                )
            )
        return jobs
