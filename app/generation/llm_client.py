import logging
from typing import Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Ollama could not be reached (not running, wrong URL, or timed out)."""


class LLMResponseError(Exception):
    """Ollama answered, but with an error or a reply we could not read."""


class LLMClient(Protocol):
    model: str

    def generate(self, system: str, prompt: str) -> str: ...


class OllamaClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None):
        self.model = settings.ollama_model
        self.url = f"{settings.ollama_url}/api/chat"
        self.temperature = settings.temperature
        self.http = http_client or httpx.Client(timeout=settings.llm_timeout_s)

    def generate(self, system: str, prompt: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        try:
            response = self.http.post(self.url, json=body)
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(f"Ollama timed out at {self.url}") from exc
        except httpx.TransportError as exc:
            raise LLMUnavailableError(f"Cannot reach Ollama at {self.url}. Is it running?") from exc

        if response.status_code == 404:
            raise LLMResponseError(f"Model {self.model!r} not found. Run: ollama pull {self.model}")
        if response.status_code != 200:
            raise LLMResponseError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")

        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMResponseError("Ollama reply did not contain message.content") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("Ollama returned an empty answer")
        return content.strip()


class FakeLLMClient:
    """Test double: returns a canned answer and remembers what it was asked."""

    def __init__(self, answer: str = "", model: str = "fake-llm"):
        self.answer = answer
        self.model = model
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        return self.answer
