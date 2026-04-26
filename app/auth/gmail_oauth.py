from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet

from app.config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailOAuthError(Exception):
    """Raised for Gmail OAuth errors."""


# Module-level fallback key so encrypt/decrypt are symmetric within a process
_FALLBACK_KEY: bytes = Fernet.generate_key()


def _make_fernet() -> Fernet:
    """Create Fernet from settings.fernet_key. If key empty/invalid, use stable module-level key."""
    key = settings.fernet_key.strip()
    if key:
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            return Fernet(_FALLBACK_KEY)
    return Fernet(_FALLBACK_KEY)


def encrypt_token(data: dict) -> str:
    """Encrypt dict -> base64 str."""
    f = _make_fernet()
    raw = json.dumps(data).encode()
    return f.encrypt(raw).decode()


def decrypt_token(blob: str | bytes) -> dict:
    """Decrypt base64 str -> dict."""
    f = _make_fernet()
    if isinstance(blob, str):
        blob_bytes = blob.encode()
    else:
        blob_bytes = blob
    decrypted = f.decrypt(blob_bytes)
    return json.loads(decrypted.decode())


# Keep _encrypt/_decrypt as aliases for backward compatibility
def _encrypt(data: dict) -> str:
    return encrypt_token(data)


def _decrypt(blob: str | bytes) -> dict:
    return decrypt_token(blob)


class GmailOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorize_url(self, state: str) -> str:
        """Return Google OAuth2 authorization URL including client_id, redirect_uri, scope, state."""
        # Encode everything except state so the raw state value is literally present in the URL
        base_params = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": GMAIL_SCOPE,
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        return f"{GOOGLE_AUTH_URL}?{base_params}&state={state}"

    def exchange_code(
        self,
        code: str,
        state: str,
        db: Any = None,
        user_id: uuid.UUID | None = None,
    ) -> dict:
        """POST to GOOGLE_TOKEN_URL with code. Store encrypted token dict in DB if db provided."""
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_data = response.json()

        if db is not None:
            encrypted = encrypt_token(token_data)
            from app.models.gmail_token import GmailToken

            token_record = GmailToken(
                user_id=user_id or uuid.uuid4(),
                encrypted_blob=encrypted,
            )
            db.add(token_record)
            db.commit()

        return token_data

    def refresh_token(
        self,
        token: dict,
        db_record: Any = None,
    ) -> dict:
        """POST to GOOGLE_TOKEN_URL with refresh_token. Return updated token dict."""
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": token.get("refresh_token", ""),
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
        )
        if not response.ok:
            raise GmailOAuthError(
                f"Token refresh failed: {response.status_code} {response.json()}"
            )

        new_token_data = response.json()
        # Merge new data into old token (keep refresh_token if not returned)
        updated_token = dict(token)
        updated_token.update(new_token_data)

        if db_record is not None:
            db_record.token_blob = encrypt_token(updated_token)

        return updated_token


async def exchange_code(
    code: str,
    state: str,
    session: Any,
    user_id: uuid.UUID,
) -> None:
    """
    POST to GOOGLE_TOKEN_URL with code. Store encrypted token dict in DB (GmailToken model).
    If GmailToken row already exists for user, UPDATE it.
    """
    import httpx
    from sqlalchemy import select
    from app.models.gmail_token import GmailToken

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.gmail_oauth_client_id,
                "client_secret": settings.gmail_oauth_client_secret,
                "redirect_uri": settings.gmail_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        token_data = response.json()

    encrypted = encrypt_token(token_data)

    result = await session.execute(select(GmailToken).where(GmailToken.user_id == user_id))
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.encrypted_blob = encrypted
    else:
        token_record = GmailToken(user_id=user_id, encrypted_blob=encrypted)
        session.add(token_record)

    await session.commit()


async def refresh_token(session: Any, user_id: uuid.UUID) -> str:
    """
    Load GmailToken for user, decrypt, POST to GOOGLE_TOKEN_URL with refresh_token.
    Update DB with new access_token. Return new access_token.
    """
    import httpx
    from sqlalchemy import select
    from app.models.gmail_token import GmailToken

    result = await session.execute(select(GmailToken).where(GmailToken.user_id == user_id))
    token_record = result.scalar_one()
    token_data = decrypt_token(token_record.encrypted_blob)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": token_data.get("refresh_token", ""),
                "client_id": settings.gmail_oauth_client_id,
                "client_secret": settings.gmail_oauth_client_secret,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        new_token_data = response.json()

    token_data.update(new_token_data)
    token_record.encrypted_blob = encrypt_token(token_data)
    await session.commit()

    return token_data["access_token"]


async def get_valid_token(session: Any, user_id: uuid.UUID) -> str:
    """Return valid access_token, auto-refreshing if expired."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.gmail_token import GmailToken

    result = await session.execute(select(GmailToken).where(GmailToken.user_id == user_id))
    token_record = result.scalar_one()
    token_data = decrypt_token(token_record.encrypted_blob)

    now = datetime.now(tz=timezone.utc)
    if token_record.expires_at is not None and token_record.expires_at <= now:
        return await refresh_token(session, user_id)

    return token_data["access_token"]
