"""
Models — Pydantic request/response models for the BM25 Search API.
"""

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class AddDocumentRequest(BaseModel):
    content: str = Field(min_length=1, description="Text content to index")
    source: str = Field(default="", description="Source file or URL")
    collection: str = Field(default="default", description="Collection namespace")
    metadata: dict = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "content": "BM25 is the standard keyword ranking algorithm used by Elasticsearch.",
                "source": "search_docs.txt",
                "collection": "search_docs",
                "metadata": {"chapter": 3},
            }
        }
    }


class AddBatchRequest(BaseModel):
    documents: list[AddDocumentRequest] = Field(
        min_length=1,
        max_length=1000,
    )


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, description="Search query string")
    k: int = Field(default=10, ge=1, le=100, description="Max results")
    collection: str | None = Field(default=None, description="Filter to collection")
    min_score: float = Field(default=0.0, ge=0.0, description="Min BM25 score")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "retrieval augmented generation",
                "k": 5,
                "collection": "rag_docs",
                "min_score": 0.5,
            }
        }
    }


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------

class DocumentResponse(BaseModel):
    doc_id: int
    content: str
    source: str
    collection: str
    metadata: dict
    token_count: int


class AddDocumentResponse(BaseModel):
    doc_id: int
    token_count: int
    message: str


class AddBatchResponse(BaseModel):
    inserted: int
    doc_ids: list[int]


class SearchResultResponse(BaseModel):
    doc_id: int
    score: float
    matched_terms: list[str]
    content: str
    source: str
    collection: str
    metadata: dict
    token_count: int


class SearchResponse(BaseModel):
    query: str
    query_tokens: list[str]
    k: int
    returned: int
    collection_filter: str | None
    results: list[SearchResultResponse]


class DeleteResponse(BaseModel):
    doc_id: int
    message: str


class StatsResponse(BaseModel):
    num_documents: int
    num_terms: int
    avg_document_length: float
    total_tokens: int
    collections: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    num_documents: int
    num_terms: int


class SaveLoadResponse(BaseModel):
    message: str
    path: str
