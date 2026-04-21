from __future__ import annotations
import urllib.robotparser
from urllib.parse import urlparse

import httpx

_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def can_fetch(url: str, user_agent: str = "*") -> bool:
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    if domain not in _cache:
        robots_url = f"{domain}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            resp = httpx.get(robots_url, timeout=5)
            rp.parse(resp.text.splitlines())
        except Exception:
            return True
        _cache[domain] = rp
    return _cache[domain].can_fetch(user_agent, url)
