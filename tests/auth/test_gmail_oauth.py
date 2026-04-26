"""Gmail OAuth tests — B.2 spec.

Tests for:
- Authorize URL generation (mocked)
- Callback code→token exchange → Fernet-encrypted blob stored in DB; round-trip decrypt
- Token refresh on expiry → DB updated
- @given property-based: random state param → authorize URL always contains state
"""
from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st
from pydantic import BaseModel
from polyfactory.factories.pydantic_factory import ModelFactory


# ---------------------------------------------------------------------------
# Token model + factory (polyfactory-compatible)
# ---------------------------------------------------------------------------


class OAuthTokenModel(BaseModel):
    """Pydantic model representing a Google OAuth token response."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    scope: str


class OAuthTokenFactory(ModelFactory):
    """polyfactory factory for OAuthTokenModel."""

    __model__ = OAuthTokenModel

    access_token = lambda: f"ya29.{uuid.uuid4().hex}"  # noqa: E731
    refresh_token = lambda: f"1//0{uuid.uuid4().hex}"  # noqa: E731
    token_type = "Bearer"
    expires_in = 3600
    scope = "https://www.googleapis.com/auth/gmail.send"


def _make_token(**kwargs: Any) -> dict:
    """Return an OAuth token dict, optionally with extra fields."""
    base = OAuthTokenFactory.build().model_dump()
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# 1. Authorize URL generation
# ---------------------------------------------------------------------------


class TestAuthorizeUrl:
    """GmailOAuth.get_authorize_url returns a URL containing required OAuth params."""

    def test_authorize_url_contains_redirect_uri(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth  # ImportError until impl

        oauth = GmailOAuth(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://example.com/callback",
        )
        url = oauth.get_authorize_url(state="test-state")
        assert "redirect_uri" in url

    def test_authorize_url_contains_client_id(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="my-client-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/cb",
        )
        url = oauth.get_authorize_url(state="s1")
        assert "my-client-id" in url

    def test_authorize_url_is_google_oauth_endpoint(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        url = oauth.get_authorize_url(state="abc")
        assert "accounts.google.com" in url or "oauth2" in url.lower()

    def test_authorize_url_contains_state_param(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        state = "my-random-state-xyz"
        url = oauth.get_authorize_url(state=state)
        assert state in url

    def test_authorize_url_contains_gmail_scope(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        url = oauth.get_authorize_url(state="s")
        # Must request gmail send scope
        assert "gmail" in url.lower() or "mail" in url.lower()

    @given(
        st.text(
            min_size=8,
            max_size=64,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="-_",
            ),
        )
    )
    @h_settings(max_examples=40)
    def test_state_always_present_in_url(self, state: str) -> None:
        """Property: any non-empty state value always appears in the authorize URL."""
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        url = oauth.get_authorize_url(state=state)
        assert state in url, f"state={state!r} not found in URL: {url!r}"


# ---------------------------------------------------------------------------
# 2. Callback: code → token → Fernet-encrypted blob stored in DB; round-trip
# ---------------------------------------------------------------------------


class TestCallbackTokenExchange:
    """exchange_code stores Fernet-encrypted token in DB; decrypt round-trip is lossless."""

    def test_exchange_code_calls_google_token_endpoint(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        fake_token = _make_token()

        with patch("app.auth.gmail_oauth.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                ok=True,
                json=MagicMock(return_value=fake_token),
                status_code=200,
            )
            oauth.exchange_code(code="auth-code-xyz", state="s1")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            # Must hit Google token endpoint
            url_arg = (
                call_kwargs[0][0]
                if call_kwargs[0]
                else call_kwargs[1].get("url", "")
            )
            assert (
                "token" in str(url_arg).lower()
                or "googleapis" in str(url_arg).lower()
                or "accounts.google" in str(url_arg).lower()
            )

    def test_exchange_code_stores_encrypted_token_in_db(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        fake_token = _make_token()
        mock_db = MagicMock()

        with patch("app.auth.gmail_oauth.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                ok=True,
                json=MagicMock(return_value=fake_token),
                status_code=200,
            )
            oauth.exchange_code(code="auth-code-xyz", state="s1", db=mock_db)

        # DB must have been written
        assert mock_db.add.called or mock_db.execute.called or mock_db.commit.called

    def test_fernet_round_trip_recovers_original_token(self) -> None:
        """Encrypt token → store → decrypt → original dict preserved."""
        from app.auth.gmail_oauth import encrypt_token, decrypt_token

        original = _make_token()
        encrypted = encrypt_token(original)

        # Encrypted blob must not be plaintext
        assert isinstance(encrypted, (str, bytes))
        as_bytes = (
            encrypted if isinstance(encrypted, bytes) else encrypted.encode()
        )
        assert json.dumps(original).encode() not in as_bytes

        # Round-trip
        recovered = decrypt_token(encrypted)
        assert recovered["access_token"] == original["access_token"]
        assert recovered["refresh_token"] == original["refresh_token"]
        assert recovered["token_type"] == original["token_type"]

    def test_fernet_round_trip_preserves_all_keys(self) -> None:
        from app.auth.gmail_oauth import encrypt_token, decrypt_token

        original = _make_token()
        recovered = decrypt_token(encrypt_token(original))
        assert set(recovered.keys()) == set(original.keys())

    @pytest.mark.parametrize(
        "extra_field,extra_value",
        [
            ("id_token", "eyJhbGciOiJSUzI1NiJ9.test"),
            ("expiry_date", 1_700_000_000),
            ("email", "user@example.com"),
        ],
    )
    def test_fernet_round_trip_extra_fields_preserved(
        self, extra_field: str, extra_value: Any
    ) -> None:
        from app.auth.gmail_oauth import encrypt_token, decrypt_token

        token = _make_token(**{extra_field: extra_value})
        recovered = decrypt_token(encrypt_token(token))
        assert recovered[extra_field] == extra_value


# ---------------------------------------------------------------------------
# 3. Token refresh on expiry
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    """refresh_token: mock POST returns new access_token → DB record updated."""

    def test_refresh_calls_token_endpoint(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        old_token = _make_token(access_token="old-access-token")
        new_access = f"ya29.new-{uuid.uuid4().hex}"

        with patch("app.auth.gmail_oauth.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                ok=True,
                json=MagicMock(
                    return_value={"access_token": new_access, "expires_in": 3600}
                ),
                status_code=200,
            )
            result = oauth.refresh_token(token=old_token)
            mock_post.assert_called_once()

        assert result["access_token"] == new_access

    def test_refresh_updates_db_record(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        old_token = _make_token(access_token="old-token")
        new_access = f"ya29.refreshed-{uuid.uuid4().hex}"
        mock_db_record = MagicMock()
        mock_db_record.token_blob = None

        with patch("app.auth.gmail_oauth.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                ok=True,
                json=MagicMock(
                    return_value={"access_token": new_access, "expires_in": 3600}
                ),
                status_code=200,
            )
            oauth.refresh_token(token=old_token, db_record=mock_db_record)

        # DB record token_blob must have been updated
        assert mock_db_record.token_blob is not None

    def test_refresh_new_access_token_differs_from_old(self) -> None:
        from app.auth.gmail_oauth import GmailOAuth

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        old_token = _make_token(access_token="old-token-abc")
        new_access = "ya29.brand-new-token"

        with patch("app.auth.gmail_oauth.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                ok=True,
                json=MagicMock(
                    return_value={"access_token": new_access, "expires_in": 3600}
                ),
                status_code=200,
            )
            result = oauth.refresh_token(token=old_token)

        assert result["access_token"] != old_token["access_token"]

    @pytest.mark.parametrize("http_status", [400, 401, 403, 500])
    def test_refresh_raises_on_http_error(self, http_status: int) -> None:
        """Non-2xx response from token endpoint raises GmailOAuthError."""
        from app.auth.gmail_oauth import GmailOAuth, GmailOAuthError

        oauth = GmailOAuth(
            client_id="cid",
            client_secret="csecret",
            redirect_uri="https://example.com/cb",
        )
        old_token = _make_token()

        with patch("app.auth.gmail_oauth.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                ok=False,
                status_code=http_status,
                json=MagicMock(return_value={"error": "invalid_grant"}),
            )
            with pytest.raises(GmailOAuthError):
                oauth.refresh_token(token=old_token)
