"""LLM provider interface with streaming support.

Supports Gemini (default), OpenAI, Anthropic, and Ollama.
All providers expose a unified async streaming interface.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from backend.app.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


class LLMProvider(ABC):
    """Abstract LLM provider with streaming support."""

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM."""
        yield ""  # pragma: no cover

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a complete response (non-streaming)."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name for logging."""


class GeminiProvider(LLMProvider):
    """Google Gemini LLM via google-genai SDK."""

    def __init__(self, model: str, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=4096,
        )

        loop = asyncio.get_event_loop()

        # Gemini streaming
        response = await loop.run_in_executor(
            None,
            lambda: self._client.models.generate_content_stream(
                model=self._model,
                contents=prompt,
                config=config,
            ),
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=4096,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            ),
        )
        return response.text or ""


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible LLM provider."""

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = None
        for attempt in range(3):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=4096,
                    stream=True,
                )
                break
            except Exception as e:
                if attempt < 2 and ("Connection error" in str(e) or "getaddrinfo" in str(e) or "11001" in str(e)):
                    logger.warning(f"Connection error to LLM (attempt {attempt+1}/3). Retrying in {attempt+1}s...")
                    await asyncio.sleep(attempt + 1)
                    continue
                raise

        if response:
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(3):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=4096,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                if attempt < 2 and ("Connection error" in str(e) or "getaddrinfo" in str(e) or "11001" in str(e)):
                    logger.warning(f"Connection error to LLM (attempt {attempt+1}/3). Retrying in {attempt+1}s...")
                    await asyncio.sleep(attempt + 1)
                    continue
                raise
        return ""


class GroqProvider(OpenAIProvider):
    """Groq LLM provider using OpenAI-compatible endpoint."""

    FALLBACK_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    def __init__(self, model: str, api_key: str):
        super().__init__(model=model, api_key=api_key, base_url="https://api.groq.com/openai/v1")

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        try:
            async for token in super().stream(prompt, system_prompt):
                yield token
        except Exception as e:
            if "model_not_found" in str(e) or "does not exist" in str(e):
                for fallback in self.FALLBACK_MODELS:
                    if fallback != self._model:
                        logger.warning(f"Model {self._model} not found on Groq. Falling back to {fallback}")
                        self._model = fallback
                        async for token in super().stream(prompt, system_prompt):
                            yield token
                        return
            raise

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        try:
            return await super().generate(prompt, system_prompt)
        except Exception as e:
            if "model_not_found" in str(e) or "does not exist" in str(e):
                for fallback in self.FALLBACK_MODELS:
                    if fallback != self._model:
                        logger.warning(f"Model {self._model} not found on Groq. Falling back to {fallback}")
                        self._model = fallback
                        return await super().generate(prompt, system_prompt)
            raise


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, model: str, api_key: str):
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        async with self._client.messages.stream(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt or "",
            temperature=0.2,
            max_tokens=4096,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        response = await self._client.messages.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt or "",
            temperature=0.2,
            max_tokens=4096,
        )
        return response.content[0].text


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, model: str, base_url: str):
        import httpx
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120)

    @property
    def model_name(self) -> str:
        return self._model

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        import json

        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": True,
            "options": {"temperature": 0.2},
        }

        async with self._client.stream("POST", "/api/generate", json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {"temperature": 0.2},
        }

        response = await self._client.post("/api/generate", json=payload)
        return response.json().get("response", "")


# ── Factory ──────────────────────────────────────

_provider_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Factory: return (cached) LLM provider based on config."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    model = settings.llm_model.strip()

    if provider == "groq" or settings.gemini_api_key.startswith("gsk_") or getattr(settings, "groq_api_key", "").startswith("gsk_"):
        groq_key = (
            getattr(settings, "groq_api_key", "").strip()
            or (settings.gemini_api_key.strip() if settings.gemini_api_key.strip().startswith("gsk_") else "")
            or settings.openai_api_key.strip()
        )
        _provider_instance = GroqProvider(
            model=model if model else "llama-3.3-70b-versatile",
            api_key=groq_key,
        )
    elif provider == "gemini":
        _provider_instance = GeminiProvider(
            model=model,
            api_key=settings.gemini_api_key.strip(),
        )
    elif provider == "openai":
        _provider_instance = OpenAIProvider(
            model=model,
            api_key=settings.openai_api_key.strip(),
        )
    elif provider == "anthropic":
        _provider_instance = AnthropicProvider(
            model=model,
            api_key=settings.anthropic_api_key.strip(),
        )
    elif provider == "ollama":
        _provider_instance = OllamaProvider(
            model=model,
            base_url=settings.ollama_base_url.strip(),
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    logger.info(f"LLM provider: {provider} ({model})")
    return _provider_instance
