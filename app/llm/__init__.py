from __future__ import annotations

from app.llm.client import FailoverClient, LLMClient
from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient


def make_llm_client() -> FailoverClient:
    """Build the LLM failover chain: Groq key-1 → Groq key-2 → Gemini."""
    from app.config import settings

    tail: LLMClient | FailoverClient = GeminiClient()
    if settings.groq_api_key_2:
        tail = FailoverClient(GroqClient(settings.groq_api_key_2), tail)
    return FailoverClient(GroqClient(), tail)
