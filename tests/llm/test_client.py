"""Tests for app.llm.groq_client and app.services.generation.cached_complete."""
from unittest.mock import patch, MagicMock
from hypothesis import given, settings
import hypothesis.strategies as st
import pytest

from app.llm.client import LLMClient
from app.llm.groq_client import GroqClient
from app.services.generation import cached_complete  # noqa: F401 — must fail until impl exists


# ---------------------------------------------------------------------------
# 1. test_groq_client_success
# ---------------------------------------------------------------------------

def test_groq_client_success(monkeypatch):
    """GroqClient.complete returns the text the API returned."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(GroqClient, "_call_api", lambda self, p, **k: "hello")
    client = GroqClient()
    result = client.complete("hi")
    assert result == "hello"


# ---------------------------------------------------------------------------
# 2. test_retry_on_429
# ---------------------------------------------------------------------------

def test_retry_on_429(monkeypatch):
    """GroqClient retries _call_api up to 3 times on exception; succeeds on 3rd."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    call_count = 0

    def _flaky(self, _prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("429 Too Many Requests")
        return "ok"

    # Patch before instantiation so tenacity wraps the patched version.
    with patch.object(GroqClient, "_call_api", _flaky):
        client = GroqClient()
        result = client.complete("test prompt")

    assert result == "ok"
    assert call_count == 3


# ---------------------------------------------------------------------------
# 3. test_cache_hit_bypasses_api
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_bypasses_api(monkeypatch):
    """cached_complete returns cached DB response and does NOT call _call_api."""
    from app.db import AsyncSessionFactory
    from app.models.llm_call import LlmCall
    from app.llm.client import LLMClient

    prompt = "cache-hit-test-prompt-unique-xyzzy"
    prompt_hash = LLMClient.hash_prompt(prompt)

    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async with AsyncSessionFactory() as session:
        # Pre-seed cached entry
        cached_row = LlmCall(
            provider="groq",
            model="llama-3.3-70b-versatile",
            prompt_hash=prompt_hash,
            prompt=prompt,
            response="cached-response",
        )
        session.add(cached_row)
        await session.commit()

        mock_client = MagicMock(spec=GroqClient)
        mock_client._call_api = MagicMock(return_value="should-not-be-called")

        result = await cached_complete(prompt, session, mock_client)

        # Cleanup
        await session.delete(cached_row)
        await session.commit()

    assert result == "cached-response"
    mock_client._call_api.assert_not_called()


# ---------------------------------------------------------------------------
# 4. hypothesis: hash_prompt is idempotent
# ---------------------------------------------------------------------------

@given(st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_hash_prompt_idempotent(prompt: str):
    """hash_prompt(p) == hash_prompt(p) for any non-empty prompt."""
    assert LLMClient.hash_prompt(prompt) == LLMClient.hash_prompt(prompt)
