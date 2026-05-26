"""
Embedding Service — Main Application

Routes:
    GET  /health              → health check
    POST /embed               → embed a single text
    POST /embed/batch         → embed multiple texts concurrently
    POST /similarity          → cosine similarity between two texts
    GET  /cache/stats         → cache hit rate and size
    DELETE /cache             → clear the cache
"""

import asyncio
import math
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from embedder import EmbeddingCache, get_provider, PROVIDERS
from models import (
    EmbedRequest, EmbedResponse,
    EmbedBatchRequest, EmbedBatchResponse,
    SimilarityRequest, SimilarityResponse,
    CacheStatsResponse, HealthResponse,
)


# ------------------------------------------------------------------
# Shared cache — one cache instance for the whole app
# ------------------------------------------------------------------

cache = EmbeddingCache(max_size=2000)


# ------------------------------------------------------------------
# App lifecycle
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Embedding Service started. Providers: {list(PROVIDERS.keys())}")
    yield
    print("Embedding Service stopped.")


app = FastAPI(
    title="Embedding Service",
    description="Convert text into vector embeddings. Supports OpenAI and mock providers.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity between two vectors.

    = dot(a, b) / (|a| * |b|)

    Returns a value between -1 and 1:
        1.0  = identical direction (same meaning)
        0.0  = orthogonal (unrelated)
       -1.0  = opposite direction (opposite meaning)

    For unit-normalized embeddings (what all providers return),
    this simplifies to just the dot product.
    """
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / (mag_a * mag_b), 6)


def interpret_similarity(score: float) -> str:
    if score >= 0.90:
        return "Very high similarity — likely the same or near-identical meaning"
    elif score >= 0.75:
        return "High similarity — closely related topics"
    elif score >= 0.50:
        return "Moderate similarity — some shared concepts"
    elif score >= 0.25:
        return "Low similarity — loosely related"
    else:
        return "Very low similarity — likely unrelated"


def get_provider_or_422(provider_name: str):
    """Get a provider instance or raise 422 with a clear message."""
    try:
        return get_provider(provider_name, cache=cache)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Public endpoint — no auth required."""
    return HealthResponse(
        status="ok",
        providers=list(PROVIDERS.keys()),
        cache_size=cache.size,
    )


@app.post(
    "/embed",
    response_model=EmbedResponse,
    status_code=status.HTTP_200_OK,
    tags=["Embeddings"],
)
async def embed_single(
    body: EmbedRequest,
    _: str = Security(verify_api_key),
):
    """
    Embed a single text and return its vector.

    Results are cached — repeated requests for the same text
    return immediately without calling the embedding API.
    """
    provider = get_provider_or_422(body.provider)

    try:
        result = await provider.embed(body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding provider error: {e}")

    return EmbedResponse(**result.to_dict())


@app.post(
    "/embed/batch",
    response_model=EmbedBatchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Embeddings"],
)
async def embed_batch(
    body: EmbedBatchRequest,
    _: str = Security(verify_api_key),
):
    """
    Embed multiple texts concurrently.

    Uses asyncio.gather with a semaphore to limit concurrent API calls.
    Cache hits are returned immediately without counting toward concurrency.
    """
    provider = get_provider_or_422(body.provider)

    try:
        batch_result = await provider.embed_batch(
            texts=body.texts,
            concurrency=body.concurrency,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding provider error: {e}")

    return EmbedBatchResponse(**batch_result.to_dict())


@app.post(
    "/similarity",
    response_model=SimilarityResponse,
    status_code=status.HTTP_200_OK,
    tags=["Embeddings"],
)
async def compute_similarity(
    body: SimilarityRequest,
    _: str = Security(verify_api_key),
):
    """
    Compute cosine similarity between two texts.

    Embeds both texts (using cache if available) then computes
    their cosine similarity score.
    """
    provider = get_provider_or_422(body.provider)

    try:
        result_a, result_b = await asyncio.gather(
            provider.embed(body.text_a),
            provider.embed(body.text_b),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    score = cosine_similarity(result_a.embedding, result_b.embedding)

    return SimilarityResponse(
        text_a_preview=body.text_a[:100],
        text_b_preview=body.text_b[:100],
        cosine_similarity=score,
        interpretation=interpret_similarity(score),
    )


@app.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    tags=["Cache"],
)
def get_cache_stats(_: str = Security(verify_api_key)):
    """Return cache hit rate and current size."""
    return CacheStatsResponse(**cache.stats())


@app.delete(
    "/cache",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Cache"],
)
def clear_cache(_: str = Security(verify_api_key)):
    """Clear all cached embeddings."""
    cache.clear()
