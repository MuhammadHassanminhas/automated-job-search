from __future__ import annotations
from app.scrapers.base import RawJob


def _key(job: RawJob) -> str:
    return f"{job.company.lower().strip()}|{job.title.lower().strip()}|{(job.location or '').lower().strip()}"


def dedup_jobs(jobs: list[RawJob]) -> list[RawJob]:
    seen: dict[str, RawJob] = {}
    for job in jobs:
        k = _key(job)
        if k not in seen:
            seen[k] = job
        else:
            existing = seen[k]
            if job.discovered_at and (
                not existing.discovered_at or job.discovered_at < existing.discovered_at
            ):
                seen[k] = job
    return list(seen.values())
