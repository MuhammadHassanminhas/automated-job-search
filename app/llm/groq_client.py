from __future__ import annotations
from typing import Any

from app.config import settings
from app.llm.client import LLMClient

try:
    from groq import Groq
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    _GROQ_AVAILABLE = True
    _TENACITY_AVAILABLE = True
except ImportError:
    try:
        from groq import Groq  # type: ignore[no-redef]
        _GROQ_AVAILABLE = True
        _TENACITY_AVAILABLE = False
    except ImportError:
        _GROQ_AVAILABLE = False
        _TENACITY_AVAILABLE = False


def _make_retry_decorator():  # type: ignore[return]
    if _TENACITY_AVAILABLE:
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=10),
            retry=retry_if_exception_type(Exception),
        )
    return None


class GroqClient(LLMClient):
    MODEL = "llama-3.3-70b-versatile"

    def __init__(self) -> None:
        if not _GROQ_AVAILABLE:
            raise ImportError("groq package not installed")
        self._client = Groq(api_key=settings.groq_api_key)
        _dec = _make_retry_decorator()
        if _dec is not None:
            self._call_api = _dec(self._call_api)  # type: ignore[method-assign]

    def _call_api(self, prompt: str, **kwargs: Any) -> str:
        response = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content or ""
