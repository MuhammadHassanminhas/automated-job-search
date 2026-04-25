"""Gemini failover tests — B.1 spec."""
from __future__ import annotations

import httpx
from unittest.mock import MagicMock

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com"


def _groq_429_response() -> httpx.Response:
    return httpx.Response(
        429,
        json={"error": {"message": "Rate limit reached", "type": "rate_limit_error"}},
    )


def _gemini_success_response(content: str = "Gemini response") -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": content}], "role": "model"}, "finishReason": "STOP"}
        ]
    }


class TestGeminiFailover:
    """When Groq returns 429, the FailoverClient must call Gemini and return its result."""

    def test_groq_429_triggers_gemini_fallback(self) -> None:
        """
        Groq returns 429 → FailoverClient calls Gemini → final result is from Gemini.
        Both Groq call AND Gemini call must have happened (asserted via call count).
        """
        from app.llm.client import FailoverClient

        primary = MagicMock()
        primary.complete = MagicMock(side_effect=Exception("429 rate limit"))
        fallback = MagicMock()
        fallback.complete = MagicMock(return_value="Gemini fallback response")

        client = FailoverClient(primary=primary, fallback=fallback)
        result = client.complete("test prompt")

        assert primary.complete.call_count == 1, "Primary (Groq) must have been called"
        assert fallback.complete.call_count == 1, "Fallback (Gemini) must have been called"
        assert result == "Gemini fallback response"

    def test_groq_success_does_not_call_gemini(self) -> None:
        """If Groq succeeds, Gemini is never called."""
        from app.llm.client import FailoverClient

        primary = MagicMock()
        primary.complete = MagicMock(return_value="Groq response")
        fallback = MagicMock()
        fallback.complete = MagicMock(return_value="Gemini response")

        client = FailoverClient(primary=primary, fallback=fallback)
        result = client.complete("test prompt")

        assert primary.complete.call_count == 1
        assert fallback.complete.call_count == 0
        assert result == "Groq response"

    def test_provider_name_is_groq_on_success(self) -> None:
        """FailoverClient.provider_name reflects which provider actually responded."""
        from app.llm.client import FailoverClient

        primary = MagicMock()
        primary.complete = MagicMock(return_value="ok")
        primary.provider_name = "groq"
        fallback = MagicMock()
        fallback.provider_name = "gemini"

        client = FailoverClient(primary=primary, fallback=fallback)
        client.complete("prompt")
        assert client.provider_name == "groq"

    def test_provider_name_is_gemini_on_failover(self) -> None:
        """After fallover, provider_name must be 'gemini'."""
        from app.llm.client import FailoverClient

        primary = MagicMock()
        primary.complete = MagicMock(side_effect=Exception("429"))
        primary.provider_name = "groq"
        fallback = MagicMock()
        fallback.complete = MagicMock(return_value="from gemini")
        fallback.provider_name = "gemini"

        client = FailoverClient(primary=primary, fallback=fallback)
        client.complete("prompt")
        assert client.provider_name == "gemini"

    def test_gemini_client_is_importable(self) -> None:
        """GeminiClient can be imported without error."""
        from app.llm.gemini_client import GeminiClient
        assert GeminiClient is not None

    def test_gemini_client_is_llm_client_subclass(self) -> None:
        """GeminiClient inherits from LLMClient."""
        from app.llm.gemini_client import GeminiClient
        from app.llm.client import LLMClient
        assert issubclass(GeminiClient, LLMClient)
