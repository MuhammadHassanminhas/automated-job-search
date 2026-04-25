from __future__ import annotations
import hashlib
from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    @staticmethod
    def hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()

    @abstractmethod
    def _call_api(self, prompt: str, **kwargs: Any) -> str: ...

    def complete(self, prompt: str, **kwargs: Any) -> str:
        # Cache logic deferred to async service layer; sync path calls API directly
        return self._call_api(prompt, **kwargs)


class FailoverClient:
    """Wraps a primary and fallback LLM client; falls back on any primary error."""

    def __init__(self, primary: Any, fallback: Any) -> None:
        self.primary = primary
        self.fallback = fallback
        _pn = getattr(primary, "provider_name", None)
        self.provider_name: str = _pn if isinstance(_pn, str) else "groq"

    def complete(self, prompt: str) -> str:
        try:
            result = self.primary.complete(prompt)
            _pn = getattr(self.primary, "provider_name", None)
            self.provider_name = _pn if isinstance(_pn, str) else "groq"
            return result
        except Exception:
            result = self.fallback.complete(prompt)
            _pn = getattr(self.fallback, "provider_name", None)
            self.provider_name = _pn if isinstance(_pn, str) else "gemini"
            return result
