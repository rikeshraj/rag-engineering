"""
Models

Pydantic request/response models for the Vector Store API.
"""

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class InsertRequest(BaseModel):
    """Body for POST /documents"""
    content: str = Field(min_length=1, description="Text content of the chunk")
    embedding: list[float] = Field(
        min_length=1,
        max_length=3072,
        description="Vector embedding (must match the model's dimensions)",
    )
    source: str = Field(default="", description="Source file or URL")
    collection: str = Field(
        default="default",
        max_length=100,
        description="Collection namespace (like a folder)",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Any extra key-value metadata",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "content": "RAG combines retrieval with generation.",
                "embedding": [0.1, -0.2, 0.05],
                "source": "rag_intro.pdf",
                "collection": "rag_docs",
                "metadata": {"page": 1, "chunk_index": 0},
            }
        }
    }


class InsertBatchRequest(BaseModel):
    """Body for POST /documents/batch"""
    documents: list[InsertRequest] = Field(
        min_length=1,
        max_length=500,
        description="List of documents to insert (max 500)",
    )


class SearchRequest(BaseModel):
    """Body for POST /search"""
    embedding: list[float] = Field(
        min_length=1,
        max_length=3072,
        description="Query vector to search with",
    )
    k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of results to return (default: 5)",
    )
    collection: str | None = Field(
        default=None,
        description="Filter to this collection only",
    )
    source: str | None = Field(
        default=None,
        description="Filter to this source only",
    )
    min_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score (0.0 = return all)",
    )
    include_embedding: bool = Field(
        default=False,
        description="Include embedding vectors in response (large — off by default)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "embedding": [0.1, -0.2, 0.05],
                "k": 5,
                "collection": "rag_docs",
                "min_score": 0.5,
                "include_embedding": False,
            }
        }
    }


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------

class DocumentResponse(BaseModel):
    """Single document — returned by insert and get routes."""
    id: int
    content: str
    source: str
    collection: str
    metadata: dict
    created_at: str
    embedding: list[float] | None = None


class InsertBatchResponse(BaseModel):
    """Response for POST /documents/batch"""
    inserted: int
    documents: list[DocumentResponse]


class SearchResultResponse(BaseModel):
    """Single search result with similarity score."""
    id: int
    content: str
    source: str
    collection: str
    metadata: dict
    created_at: str
    score: float
    embedding: list[float] | None = None


class SearchResponse(BaseModel):
    """Response for POST /search"""
    query_k: int
    returned: int
    collection_filter: str | None
    source_filter: str | None
    results: list[SearchResultResponse]


class DeleteResponse(BaseModel):
    id: int
    message: str


class DeleteCollectionResponse(BaseModel):
    collection: str
    deleted_count: int
    message: str


class CollectionInfo(BaseModel):
    collection: str
    document_count: int
    created_at: str
    updated_at: str


class StatsResponse(BaseModel):
    total_documents: int
    collections: list[CollectionInfo]


class HealthResponse(BaseModel):
    status: str
    total_documents: int
