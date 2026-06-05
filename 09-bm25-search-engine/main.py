"""
BM25 Search Engine — Main Application

Routes:
    GET    /health                  → health check
    POST   /documents               → index one document
    POST   /documents/batch         → index many documents
    GET    /documents/{id}          → get document by ID
    DELETE /documents/{id}          → remove document from index
    POST   /search                  → BM25 keyword search
    GET    /stats                   → index statistics
    POST   /index/save              → persist index to disk
    POST   /index/load              → restore index from disk
    DELETE /index                   → clear the entire index
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from engine import SearchEngine
from models import (
    AddDocumentRequest, AddBatchRequest, SearchRequest,
    DocumentResponse, AddDocumentResponse, AddBatchResponse,
    SearchResponse, SearchResultResponse,
    DeleteResponse, StatsResponse, HealthResponse, SaveLoadResponse,
)

# ------------------------------------------------------------------
# Shared engine instance
# ------------------------------------------------------------------

INDEX_PATH = Path(os.getenv("INDEX_PATH", "bm25_index.json"))

engine = SearchEngine(
    k1=float(os.getenv("BM25_K1", "1.5")),
    b=float(os.getenv("BM25_B", "0.75")),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-load index on startup if it exists
    if INDEX_PATH.exists():
        try:
            engine.load(INDEX_PATH)
            print(f"Loaded index from {INDEX_PATH} "
                  f"({engine.index.num_documents} documents)")
        except Exception as e:
            print(f"Warning: could not load index: {e}")
    yield
    # Auto-save on shutdown
    try:
        engine.save(INDEX_PATH)
        print(f"Index saved to {INDEX_PATH}")
    except Exception as e:
        print(f"Warning: could not save index: {e}")


app = FastAPI(
    title="BM25 Search Engine",
    description=(
        "Keyword search using the BM25 ranking algorithm. "
        "Pure Python — no Elasticsearch required."
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
# Health
# ------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    stats = engine.stats()
    return HealthResponse(
        status="ok",
        num_documents=stats["num_documents"],
        num_terms=stats["num_terms"],
    )


# ------------------------------------------------------------------
# Index documents
# ------------------------------------------------------------------

@app.post(
    "/documents",
    response_model=AddDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def add_document(
    body: AddDocumentRequest,
    _: str = Security(verify_api_key),
):
    """Tokenize and index a single document."""
    doc_id = engine.add_document(
        content=body.content,
        source=body.source,
        collection=body.collection,
        metadata=body.metadata,
    )
    doc = engine.get_document(doc_id)
    return AddDocumentResponse(
        doc_id=doc_id,
        token_count=doc.token_count,
        message="Document indexed successfully.",
    )


@app.post(
    "/documents/batch",
    response_model=AddBatchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def add_batch(
    body: AddBatchRequest,
    _: str = Security(verify_api_key),
):
    """Index multiple documents at once."""
    docs_data = [
        {
            "content":    d.content,
            "source":     d.source,
            "collection": d.collection,
            "metadata":   d.metadata,
        }
        for d in body.documents
    ]
    doc_ids = engine.add_batch(docs_data)
    return AddBatchResponse(inserted=len(doc_ids), doc_ids=doc_ids)


# ------------------------------------------------------------------
# Get / Remove
# ------------------------------------------------------------------

@app.get(
    "/documents/{doc_id}",
    response_model=DocumentResponse,
    tags=["Documents"],
)
def get_document(doc_id: int, _: str = Security(verify_api_key)):
    doc = engine.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found.",
        )
    return DocumentResponse(**doc.to_dict())


@app.delete(
    "/documents/{doc_id}",
    response_model=DeleteResponse,
    tags=["Documents"],
)
def remove_document(doc_id: int, _: str = Security(verify_api_key)):
    removed = engine.remove_document(doc_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found.",
        )
    return DeleteResponse(doc_id=doc_id, message="Document removed from index.")


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

@app.post("/search", response_model=SearchResponse, tags=["Search"])
def search(
    body: SearchRequest,
    _: str = Security(verify_api_key),
):
    """
    BM25 keyword search.

    The query is tokenized with the same pipeline used at index time.
    Results are ranked by BM25 score — higher = more relevant.
    Each result shows which query terms matched.
    """
    query_tokens = engine.tokenizer.tokenize_query(body.query)
    results = engine.search(
        query=body.query,
        k=body.k,
        collection=body.collection,
        min_score=body.min_score,
    )

    return SearchResponse(
        query=body.query,
        query_tokens=query_tokens,
        k=body.k,
        returned=len(results),
        collection_filter=body.collection,
        results=[
            SearchResultResponse(
                doc_id=r.doc_id,
                score=r.score,
                matched_terms=r.matched_terms,
                content=r.document.content,
                source=r.document.source,
                collection=r.document.collection,
                metadata=r.document.metadata,
                token_count=r.document.token_count,
            )
            for r in results
        ],
    )


# ------------------------------------------------------------------
# Stats / Persistence
# ------------------------------------------------------------------

@app.get("/stats", response_model=StatsResponse, tags=["System"])
def get_stats(_: str = Security(verify_api_key)):
    return StatsResponse(**engine.stats())


@app.post("/index/save", response_model=SaveLoadResponse, tags=["Index"])
def save_index(_: str = Security(verify_api_key)):
    """Save the current index to disk."""
    try:
        engine.save(INDEX_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SaveLoadResponse(
        message=f"Index saved ({engine.index.num_documents} documents).",
        path=str(INDEX_PATH),
    )


@app.post("/index/load", response_model=SaveLoadResponse, tags=["Index"])
def load_index(_: str = Security(verify_api_key)):
    """Load the index from disk."""
    if not INDEX_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No index file found at {INDEX_PATH}.",
        )
    try:
        engine.load(INDEX_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SaveLoadResponse(
        message=f"Index loaded ({engine.index.num_documents} documents).",
        path=str(INDEX_PATH),
    )


@app.delete("/index", status_code=status.HTTP_204_NO_CONTENT, tags=["Index"])
def clear_index(_: str = Security(verify_api_key)):
    """Clear the entire index."""
    engine.clear()
