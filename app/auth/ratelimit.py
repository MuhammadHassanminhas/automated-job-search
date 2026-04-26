from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request as _Request


def _client_ip(request: _Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_client_ip)

__all__ = ["limiter", "RateLimitExceeded"]
