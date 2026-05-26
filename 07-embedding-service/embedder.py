"""
Embedder

Converts text into vector embeddings using pluggable providers.

Providers:
    openai  — OpenAI text-embedding-3-small (1536 dims, requires API key)
    mock    — Deterministic fake embeddings (for testing, no API key needed)

All providers share the same interface:
    embed(text)           → list[float]
    embed_batch(texts)    → list[list[float]]
"""

import asyncio
import hashlib
import math
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class EmbeddingResult:
    """
    Result for a single text embedding.

    text          — the original input text
    embedding     — the vector (list of floats)
    provider      — which provider generated this
    model         — model name used
    dimensions    — length of the embedding vector
    token_count   — tokens consumed (if known)
    latency_ms    — how long the API call took
    cached        — whether this came from cache
    """
    text: str
    embedding: list[float]
    provider: str
    model: str
    dimensions: int
    token_count: int = 0
    latency_ms: float = 0.0
    cached: bool = False

    def to_dict(self) -> dict:
        return {
            "text_preview":  self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "provider":      self.provider,
            "model":         self.model,
            "dimensions":    self.dimensions,
            "token_count":   self.token_count,
            "latency_ms":    round(self.latency_ms, 2),
            "cached":        self.cached,
            "embedding":     self.embedding,
        }


@dataclass
class BatchEmbeddingResult:
    """Result for a batch of texts."""
    results: list[EmbeddingResult]
    provider: str
    model: str
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    cache_hits: int = 0

    @property
    def total_texts(self) -> int:
        return len(self.results)

    @property
    def embeddings(self) -> list[list[float]]:
        """Just the vectors, in order."""
        return [r.embedding for r in self.results]

    def to_dict(self) -> dict:
        return {
            "provider":         self.provider,
            "model":            self.model,
            "total_texts":      self.total_texts,
            "total_tokens":     self.total_tokens,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "cache_hits":       self.cache_hits,
            "results":          [r.to_dict() for r in self.results],
        }


# ------------------------------------------------------------------
# Cache
# ------------------------------------------------------------------

class EmbeddingCache:
    """
    Simple in-memory LRU-style cache for embeddings.

    Key: SHA-256 hash of (provider + model + text)
    Value: list[float] embedding

    Why hash the key?
    - Text can be very long — using it directly as a dict key is wasteful
    - SHA-256 gives a fixed 64-char key regardless of text length
    - Collision probability is negligible (~10^-77)
    """

    def __init__(self, max_size: int = 1000):
        self._store: dict[str, list[float]] = {}
        self._max_size = max_size
        self.hits = 0
        self.misses = 0

    def _make_key(self, provider: str, model: str, text: str) -> str:
        raw = f"{provider}:{model}:{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, provider: str, model: str, text: str) -> list[float] | None:
        key = self._make_key(provider, model, text)
        result = self._store.get(key)
        if result is not None:
            self.hits += 1
        else:
            self.misses += 1
        return result

    def set(self, provider: str, model: str, text: str, embedding: list[float]) -> None:
        if len(self._store) >= self._max_size:
            # Evict oldest entry (first key inserted — Python dicts preserve order)
            oldest = next(iter(self._store))
            del self._store[oldest]
        key = self._make_key(provider, model, text)
        self._store[key] = embedding

    def clear(self) -> None:
        self._store.clear()
        self.hits = 0
        self.misses = 0

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "size":     self.size,
            "max_size": self._max_size,
            "hits":     self.hits,
            "misses":   self.misses,
            "hit_rate": self.hit_rate,
        }


# ------------------------------------------------------------------
# Base provider
# ------------------------------------------------------------------

class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for all embedding providers.

    Subclasses must implement:
        _embed_single(text)  — embed one text, return list[float]

    embed() and embed_batch() are implemented here and handle
    caching, timing, and async concurrency automatically.
    """

    def __init__(self, cache: EmbeddingCache | None = None):
        self.cache = cache or EmbeddingCache()

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier string for this provider."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier used for cache keys and metadata."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Length of the embedding vector this provider returns."""

    @abstractmethod
    async def _embed_single(self, text: str) -> tuple[list[float], int]:
        """
        Embed a single text. Returns (embedding, token_count).
        Must be implemented by each provider.
        """

    async def embed(self, text: str) -> EmbeddingResult:
        """
        Embed a single text with caching and timing.
        Checks cache first — calls API only on cache miss.
        """
        text = text.strip()
        if not text:
            raise ValueError("Cannot embed empty text.")

        # Cache lookup
        cached = self.cache.get(self.provider_name, self.model_name, text)
        if cached is not None:
            return EmbeddingResult(
                text=text,
                embedding=cached,
                provider=self.provider_name,
                model=self.model_name,
                dimensions=self.dimensions,
                cached=True,
            )

        # API call
        start = time.perf_counter()
        embedding, token_count = await self._embed_single(text)
        latency_ms = (time.perf_counter() - start) * 1000

        # Store in cache
        self.cache.set(self.provider_name, self.model_name, text, embedding)

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            provider=self.provider_name,
            model=self.model_name,
            dimensions=self.dimensions,
            token_count=token_count,
            latency_ms=latency_ms,
            cached=False,
        )

    async def embed_batch(
        self,
        texts: list[str],
        concurrency: int = 5,
    ) -> BatchEmbeddingResult:
        """
        Embed a list of texts concurrently.

        concurrency controls how many API calls run simultaneously.
        Using a semaphore prevents overwhelming the API with too many
        parallel requests — important for rate limiting.
        """
        if not texts:
            raise ValueError("Cannot embed an empty list.")

        semaphore = asyncio.Semaphore(concurrency)

        async def embed_with_limit(text: str) -> EmbeddingResult:
            async with semaphore:
                return await self.embed(text)

        start = time.perf_counter()
        results = await asyncio.gather(*[embed_with_limit(t) for t in texts])
        total_latency_ms = (time.perf_counter() - start) * 1000

        return BatchEmbeddingResult(
            results=list(results),
            provider=self.provider_name,
            model=self.model_name,
            total_tokens=sum(r.token_count for r in results),
            total_latency_ms=total_latency_ms,
            cache_hits=sum(1 for r in results if r.cached),
        )


# ------------------------------------------------------------------
# Provider 1: OpenAI
# ------------------------------------------------------------------

class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    Embeddings via OpenAI's text-embedding-3-small model.

    Requires: pip install openai
    Requires: OPENAI_API_KEY environment variable

    text-embedding-3-small:
        - 1536 dimensions
        - ~$0.02 per 1M tokens (very cheap)
        - Strong multilingual support
        - Best cost/quality ratio for most RAG applications
    """

    PROVIDER = "openai"
    MODEL    = "text-embedding-3-small"
    DIMS     = 1536

    def __init__(self, api_key: str | None = None, cache: EmbeddingCache | None = None):
        super().__init__(cache)
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key= to OpenAIEmbeddingProvider()."
            )
        self._client = None  # lazy init

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    @property
    def provider_name(self) -> str:
        return self.PROVIDER

    @property
    def model_name(self) -> str:
        return self.MODEL

    @property
    def dimensions(self) -> int:
        return self.DIMS

    async def _embed_single(self, text: str) -> tuple[list[float], int]:
        client = self._get_client()
        response = await client.embeddings.create(
            model=self.MODEL,
            input=text,
        )
        embedding = response.data[0].embedding
        token_count = response.usage.total_tokens
        return embedding, token_count


# ------------------------------------------------------------------
# Provider 2: Mock (for testing, no API key needed)
# ------------------------------------------------------------------

class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic fake embeddings for development and testing.

    Generates embeddings using a seeded hash of the input text.
    Same text always produces the same vector — deterministic.
    Cosine similarity between different texts will be random,
    not semantically meaningful.

    Useful for:
    - Testing the pipeline without spending API credits
    - CI/CD where no API key is available
    - Development of downstream components (vector store, retrieval)

    NOT useful for:
    - Any real retrieval — results will be semantically meaningless
    """

    PROVIDER = "mock"
    MODEL    = "mock-embedding-v1"

    def __init__(self, dimensions: int = 1536, cache: EmbeddingCache | None = None):
        super().__init__(cache)
        self._dimensions = dimensions

    @property
    def provider_name(self) -> str:
        return self.PROVIDER

    @property
    def model_name(self) -> str:
        return self.MODEL

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def _embed_single(self, text: str) -> tuple[list[float], int]:
        """
        Generate a deterministic unit-vector from the text hash.

        Process:
        1. Hash the text with SHA-256 → 32 bytes
        2. Use bytes as seed to generate `dimensions` floats
        3. L2-normalize the vector so it lies on the unit sphere
           (same normalization real embedding models use)
        """
        # Seed a simple PRNG from the text hash
        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)

        raw = []
        for i in range(self._dimensions):
            # LCG (linear congruential generator) — simple deterministic PRNG
            seed = (seed * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
            # Map to [-1, 1]
            raw.append((seed / (2 ** 64)) * 2 - 1)

        # L2 normalize — make it a unit vector
        magnitude = math.sqrt(sum(x * x for x in raw))
        embedding = [x / magnitude for x in raw]

        # Simulate a small network delay
        await asyncio.sleep(0.001)

        token_count = len(text.split())
        return embedding, token_count


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

PROVIDERS = {
    "openai": OpenAIEmbeddingProvider,
    "mock":   MockEmbeddingProvider,
}


def get_provider(
    provider: str = "mock",
    cache: EmbeddingCache | None = None,
    **kwargs,
) -> BaseEmbeddingProvider:
    """
    Factory function — returns the right provider by name.

    Usage:
        provider = get_provider("mock")
        result = await provider.embed("hello world")

        provider = get_provider("openai")  # needs OPENAI_API_KEY
        batch = await provider.embed_batch(["text1", "text2"])
    """
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Choose from: {', '.join(PROVIDERS.keys())}"
        )
    return PROVIDERS[provider](cache=cache, **kwargs)
