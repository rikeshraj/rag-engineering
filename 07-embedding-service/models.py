"""
Models

Pydantic request/response models for the Embedding Service API.
"""

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class EmbedRequest(BaseModel):
    """Body for POST /embed — embed a single text."""
    text: str = Field(
        min_length=1,
        max_length=8192,
        description="Text to embed. Max 8192 characters.",
    )
    provider: str = Field(
        default="mock",
        description="Embedding provider: 'openai' or 'mock'",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Retrieval-Augmented Generation combines search with generation.",
                "provider": "mock",
            }
        }
    }


class EmbedBatchRequest(BaseModel):
    """Body for POST /embed/batch — embed multiple texts at once."""
    texts: list[str] = Field(
        min_length=1,
        max_length=100,
        description="List of texts to embed. Max 100 texts per request.",
    )
    provider: str = Field(
        default="mock",
        description="Embedding provider: 'openai' or 'mock'",
    )
    concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max concurrent API calls (default: 5)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "texts": [
                    "What is RAG?",
                    "How do embeddings work?",
                    "What is cosine similarity?",
                ],
                "provider": "mock",
                "concurrency": 5,
            }
        }
    }


class SimilarityRequest(BaseModel):
    """Body for POST /similarity — compare two texts."""
    text_a: str = Field(min_length=1, max_length=8192)
    text_b: str = Field(min_length=1, max_length=8192)
    provider: str = Field(default="mock")


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------

class EmbedResponse(BaseModel):
    """Response for POST /embed"""
    text_preview: str
    provider: str
    model: str
    dimensions: int
    token_count: int
    latency_ms: float
    cached: bool
    embedding: list[float]


class EmbedBatchResponse(BaseModel):
    """Response for POST /embed/batch"""
    provider: str
    model: str
    total_texts: int
    total_tokens: int
    total_latency_ms: float
    cache_hits: int
    results: list[EmbedResponse]


class SimilarityResponse(BaseModel):
    """Response for POST /similarity"""
    text_a_preview: str
    text_b_preview: str
    cosine_similarity: float
    interpretation: str


class CacheStatsResponse(BaseModel):
    """Response for GET /cache/stats"""
    size: int
    max_size: int
    hits: int
    misses: int
    hit_rate: float


class HealthResponse(BaseModel):
    """Response for GET /health"""
    status: str
    providers: list[str]
    cache_size: int
