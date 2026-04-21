from __future__ import annotations
import time


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self._interval = min_interval_seconds
        self._last_call: float = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_call = time.monotonic()
