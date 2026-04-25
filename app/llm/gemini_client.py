from __future__ import annotations
from typing import Any

from app.config import settings
from app.llm.client import LLMClient


class GeminiClient(LLMClient):
    provider_name: str = "gemini"
    MODEL: str = "gemini-2.0-flash-lite"

    def _call_api(self, prompt: str, **kwargs: Any) -> str:
        try:
            import google.generativeai as genai  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package is required for GeminiClient. "
                "Install it with: uv add google-generativeai"
            ) from exc
        api_key: str = getattr(settings, "gemini_api_key", "")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in .env to enable Gemini failover."
            )
        genai.configure(api_key=api_key)
        model_name: str = getattr(settings, "gemini_model", self.MODEL)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
