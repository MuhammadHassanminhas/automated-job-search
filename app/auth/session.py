from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings

_pwd_ctx = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
)
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="session")

MAX_AGE = 60 * 60 * 24 * 7  # 7 days


class InvalidSession(Exception):
    """Raised when a session cookie cannot be decoded or has been tampered with."""


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_session_cookie(payload: dict) -> str:
    return _serializer.dumps(payload)


def decode_session_cookie(cookie: str) -> dict:
    try:
        return _serializer.loads(cookie, max_age=MAX_AGE)
    except BadSignature as exc:
        raise InvalidSession("Invalid or tampered session cookie") from exc
