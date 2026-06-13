"""
Providers

LLM provider implementations with retry logic, streaming,
and token tracking.

Providers:
    anthropic — Claude models via Anthropic SDK
    mock      — Deterministic fake responses for testing

All providers share the same interface:
    complete(messages, **kwargs)         → CompletionResult
    stream(messages, **kwargs)           → AsyncGenerator[str]
"""

import asyncio
import hashlib
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator

from tokens import count_tokens_approx, estimate_cost


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class CompletionResult:
    """
    Result from a single LLM completion call.

    content       — the model's response text
    model         — model that was used
    provider      — provider name
    input_tokens  — tokens consumed by prompt
    output_tokens — tokens in model's response
    latency_ms    — total API call time
    cost          — estimated USD cost
    cached        — whether result came from cache
    stop_reason   — why the model stopped (end_turn, max_tokens, etc.)
    """
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: dict = field(default_factory=dict)
    cached: bool = False
    stop_reason: str = "end_turn"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "content":       self.content,
            "model":         self.model,
            "provider":      self.provider,
            "input_tokens":  self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens":  self.total_tokens,
            "latency_ms":    round(self.latency_ms, 2),
            "cost":          self.cost,
            "cached":        self.cached,
            "stop_reason":   self.stop_reason,
        }


# ------------------------------------------------------------------
# Retry helper
# ------------------------------------------------------------------

async def retry_with_backoff(
    coro_fn,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_errors: tuple = (),
):
    """
    Retry an async function with exponential backoff.

    Exponential backoff: wait 1s, 2s, 4s, ... between retries.
    Jitter adds randomness to prevent thundering herd —
    all clients retrying at the same time overwhelming the API.

    retryable_errors: exception types that should trigger a retry.
    Other exceptions are raised immediately.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except retryable_errors as e:
            last_error = e
            if attempt == max_retries:
                break
            delay = min(base_delay * (2 ** attempt), max_delay)
            # Add jitter: ±20% of the delay
            import random
            jitter = delay * 0.2 * (random.random() * 2 - 1)
            await asyncio.sleep(delay + jitter)
        except Exception:
            raise  # Non-retryable errors bubble up immediately

    raise last_error


# ------------------------------------------------------------------
# Base provider
# ------------------------------------------------------------------

class BaseProvider(ABC):
    """
    Abstract base for all LLM providers.

    Subclasses implement _call_api() and _stream_api().
    Base class handles retry logic, timing, and cost estimation.
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    async def _call_api(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
    ) -> CompletionResult: ...

    @abstractmethod
    async def _stream_api(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
    ) -> AsyncGenerator[str, None]: ...

    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> CompletionResult:
        """
        Complete a conversation with retry on rate limit errors.
        Returns a CompletionResult with full metadata.
        """
        model = model or self.default_model

        async def call():
            return await self._call_api(
                messages, model, max_tokens, temperature, system
            )

        start = time.perf_counter()
        result = await retry_with_backoff(
            call,
            max_retries=self.max_retries,
        )
        result.latency_ms = (time.perf_counter() - start) * 1000
        result.cost = estimate_cost(result.input_tokens, result.output_tokens, model)
        return result

    async def stream(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens as they arrive."""
        model = model or self.default_model
        async for token in self._stream_api(
            messages, model, max_tokens, temperature, system
        ):
            yield token


# ------------------------------------------------------------------
# Provider 1: Anthropic
# ------------------------------------------------------------------

class AnthropicProvider(BaseProvider):
    """
    Claude models via the Anthropic Python SDK.

    Requires: pip install anthropic
    Requires: ANTHROPIC_API_KEY environment variable

    Supports:
    - claude-sonnet-4-20250514  (best quality)
    - claude-3-5-haiku-20241022 (fastest, cheapest)
    - claude-3-opus-20240229    (most capable)
    """

    PROVIDER = "anthropic"
    DEFAULT_MODEL = "claude-3-5-haiku-20241022"

    def __init__(self, api_key: str | None = None, max_retries: int = 3):
        super().__init__(max_retries)
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Anthropic API key required. "
                "Set ANTHROPIC_API_KEY or pass api_key=."
            )
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError:
                raise ImportError("pip install anthropic")
        return self._client

    @property
    def provider_name(self) -> str:
        return self.PROVIDER

    @property
    def default_model(self) -> str:
        return self.DEFAULT_MODEL

    async def _call_api(self, messages, model, max_tokens, temperature, system):
        client = self._get_client()
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)

        return CompletionResult(
            content=response.content[0].text,
            model=model,
            provider=self.PROVIDER,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=0.0,
            stop_reason=response.stop_reason or "end_turn",
        )

    async def _stream_api(self, messages, model, max_tokens, temperature, system):
        client = self._get_client()
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if system:
            kwargs["system"] = system

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


# ------------------------------------------------------------------
# Provider 2: Mock
# ------------------------------------------------------------------

class MockProvider(BaseProvider):
    """
    Deterministic fake LLM for testing.

    Returns a predictable response based on the input —
    no API key or network needed.

    Response format: "Mock response to: <first 50 chars of last message>"
    Streaming: yields the response word by word with a small delay.
    """

    PROVIDER = "mock"
    DEFAULT_MODEL = "mock-llm-v1"

    @property
    def provider_name(self) -> str:
        return self.PROVIDER

    @property
    def default_model(self) -> str:
        return self.DEFAULT_MODEL

    async def _call_api(self, messages, model, max_tokens, temperature, system):
        # Simulate network latency
        await asyncio.sleep(0.05)

        last_msg = messages[-1].get("content", "") if messages else ""
        preview = last_msg[:50].replace("\n", " ")
        content = f"Mock response to: {preview}"

        if system:
            content = f"[System: {system[:30]}] {content}"

        # Trim to max_tokens (approximate)
        words = content.split()
        max_words = max_tokens // 4
        if len(words) > max_words:
            content = " ".join(words[:max_words])

        input_tokens  = count_tokens_approx(
            " ".join(m.get("content", "") for m in messages)
        )
        output_tokens = count_tokens_approx(content)

        return CompletionResult(
            content=content,
            model=model,
            provider=self.PROVIDER,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=0.0,
            stop_reason="end_turn",
        )

    async def _stream_api(self, messages, model, max_tokens, temperature, system):
        result = await self._call_api(messages, model, max_tokens, temperature, system)
        # Yield word by word to simulate streaming
        for word in result.content.split():
            yield word + " "
            await asyncio.sleep(0.01)


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

PROVIDERS = {
    "anthropic": AnthropicProvider,
    "mock":      MockProvider,
}


def get_provider(provider: str = "mock", **kwargs) -> BaseProvider:
    """
    Factory — returns the right provider by name.

    Usage:
        p = get_provider("mock")
        result = await p.complete([{"role": "user", "content": "Hello"}])

        p = get_provider("anthropic")  # needs ANTHROPIC_API_KEY
        result = await p.complete([{"role": "user", "content": "Hello"}])
    """
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Choose from: {', '.join(PROVIDERS.keys())}"
        )
    return PROVIDERS[provider](**kwargs)
