"""
Vector Store API — Main Application

Routes:
    GET    /health                  → health check + document count
    POST   /documents               → insert one document
    POST   /documents/batch         → insert many documents
    GET    /documents/{id}          → get document by ID
    DELETE /documents/{id}          → delete document by ID
    POST   /search                  → similarity search
    GET    /collections             → list all collections
    DELETE /collections/{name}      → delete all docs in a collection
    GET    /stats                   → total docs + collection breakdown
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from database import init_db
from models import (
    InsertRequest, InsertBatchRequest, SearchRequest,
    DocumentResponse, InsertBatchResponse,
    SearchResponse, SearchResultResponse,
    DeleteResponse, DeleteCollectionResponse,
    CollectionInfo, StatsResponse, HealthResponse,
)
import store


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Vector Store API",
    description=(
        "Store and search vector embeddings using PostgreSQL + pgvector. "
        "Supports cosine similarity search, collection namespacing, and metadata filtering."
    ),
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
# Helper
# ------------------------------------------------------------------

def doc_to_response(doc, include_embedding: bool = False) -> DocumentResponse:
    d = doc.to_dict(include_embedding=include_embedding)
    return DocumentResponse(**d)


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Public — no auth required."""
    stats = store.get_stats()
    return HealthResponse(
        status="ok",
        total_documents=stats["total_documents"],
    )


# ------------------------------------------------------------------
# Insert
# ------------------------------------------------------------------

@app.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def insert_document(
    body: InsertRequest,
    _: str = Security(verify_api_key),
):
    """Insert a single document with its embedding."""
    try:
        doc = store.insert_document(
            content=body.content,
            embedding=body.embedding,
            source=body.source,
            collection=body.collection,
            metadata=body.metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")
    return doc_to_response(doc)


@app.post(
    "/documents/batch",
    response_model=InsertBatchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def insert_batch(
    body: InsertBatchRequest,
    _: str = Security(verify_api_key),
):
    """
    Insert multiple documents in a single transaction.
    Much faster than N individual inserts for large batches.
    """
    docs_data = [
        {
            "content":    d.content,
            "embedding":  d.embedding,
            "source":     d.source,
            "collection": d.collection,
            "metadata":   d.metadata,
        }
        for d in body.documents
    ]
    try:
        docs = store.insert_batch(docs_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch insert failed: {e}")

    return InsertBatchResponse(
        inserted=len(docs),
        documents=[doc_to_response(d) for d in docs],
    )


# ------------------------------------------------------------------
# Get / Delete
# ------------------------------------------------------------------

@app.get(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    tags=["Documents"],
)
def get_document(
    doc_id: int,
    include_embedding: bool = False,
    _: str = Security(verify_api_key),
):
    """Retrieve a single document by ID."""
    doc = store.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found.",
        )
    return doc_to_response(doc, include_embedding=include_embedding)


@app.delete(
    "/documents/{doc_id}",
    response_model=DeleteResponse,
    tags=["Documents"],
)
def delete_document(
    doc_id: int,
    _: str = Security(verify_api_key),
):
    """Delete a document by ID."""
    deleted = store.delete_document(doc_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found.",
        )
    return DeleteResponse(id=doc_id, message="Document deleted.")


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

@app.post(
    "/search",
    response_model=SearchResponse,
    tags=["Search"],
)
def search(
    body: SearchRequest,
    _: str = Security(verify_api_key),
):
    """
    Find the k most similar documents to a query embedding.

    Uses cosine similarity via pgvector's <=> operator.
    Supports filtering by collection and source before searching.
    Set min_score to filter out low-quality matches.
    """
    try:
        results = store.search(
            query_embedding=body.embedding,
            k=body.k,
            collection=body.collection,
            source=body.source,
            min_score=body.min_score,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    return SearchResponse(
        query_k=body.k,
        returned=len(results),
        collection_filter=body.collection,
        source_filter=body.source,
        results=[
            SearchResultResponse(
                **r.document.to_dict(include_embedding=body.include_embedding),
                score=r.score,
            )
            for r in results
        ],
    )


# ------------------------------------------------------------------
# Collections
# ------------------------------------------------------------------

@app.get(
    "/collections",
    response_model=list[CollectionInfo],
    tags=["Collections"],
)
def list_collections(_: str = Security(verify_api_key)):
    """List all collections with document counts."""
    return [CollectionInfo(**c) for c in store.list_collections()]


@app.delete(
    "/collections/{collection_name}",
    response_model=DeleteCollectionResponse,
    tags=["Collections"],
)
def delete_collection(
    collection_name: str,
    _: str = Security(verify_api_key),
):
    """Delete all documents in a collection."""
    count = store.delete_collection(collection_name)
    return DeleteCollectionResponse(
        collection=collection_name,
        deleted_count=count,
        message=f"Deleted {count} documents from '{collection_name}'.",
    )


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

@app.get(
    "/stats",
    response_model=StatsResponse,
    tags=["System"],
)
def get_stats(_: str = Security(verify_api_key)):
    """Total document count and per-collection breakdown."""
    stats = store.get_stats()
    return StatsResponse(
        total_documents=stats["total_documents"],
        collections=[CollectionInfo(**c) for c in stats["collections"]],
    )
