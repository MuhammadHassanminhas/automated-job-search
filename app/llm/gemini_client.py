from __future__ import annotations
from typing import Any

from app.config import settings
from app.llm.client import LLMClient


class GeminiClient(LLMClient):
    provider_name: str = "gemini"
    MODEL: str = "gemini-2.0-flash-lite"

    def _call_api(self, prompt: str, **_kwargs: Any) -> str:
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "google-genai package is required for GeminiClient. "
                "Install it with: uv add google-genai"
            ) from exc
        api_key: str = getattr(settings, "gemini_api_key", "")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in .env to enable Gemini failover."
            )
        client = genai.Client(api_key=api_key)
        model_name: str = getattr(settings, "gemini_model", self.MODEL)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return response.text
