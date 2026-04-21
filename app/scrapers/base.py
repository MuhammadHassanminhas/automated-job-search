from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RawJob:
    title: str
    company: str
    location: str | None
    url: str
    description: str = ""
    external_id: str = ""
    source: str = ""
    posted_at: datetime | None = None
    remote_allowed: bool = False
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobSource(ABC):
    @abstractmethod
    def fetch(self) -> list[Any]: ...

    @abstractmethod
    def normalize(self, raw: list[Any]) -> list[RawJob]: ...

    def run(self) -> list[RawJob]:
        raw = self.fetch()
        jobs = self.normalize(raw)
        return jobs
