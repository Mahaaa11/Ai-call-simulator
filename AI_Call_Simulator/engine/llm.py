"""Ollama client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class LLMError(RuntimeError):
    """Raised when Ollama cannot produce a response."""


@dataclass
class OllamaClient:
    """Small HTTP client for Ollama chat completions."""

    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 45

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send chat messages to Ollama and return the model response."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.35,
                "top_p": 0.85,
                "num_predict": 60,
                "num_ctx": 4096,
            },
        }
        try:
            response = requests.post(
                f"{self.base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                f"Could not reach Ollama. Start Ollama and run: ollama pull {self.model}"
            ) from exc

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()
        if not content:
            raise LLMError("Ollama returned an empty customer response.")
        return content
