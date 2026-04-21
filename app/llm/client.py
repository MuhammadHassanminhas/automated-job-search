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
