"""AI provider adapter: swap providers without rewriting the app.
Default is Ollama (free, local). Add Gemini/Groq/OpenRouter adapters later."""
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class AIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str: ...


class OllamaProvider(AIProvider):
    def generate(self, prompt: str, system: str = "") -> str:
        r = httpx.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt,
                  "system": system, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["response"]


def get_provider() -> AIProvider:
    if settings.ai_provider == "ollama":
        return OllamaProvider()
    raise NotImplementedError(f"Provider '{settings.ai_provider}' not added yet")
