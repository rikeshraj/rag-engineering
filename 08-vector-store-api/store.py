"""
Store

All vector store operations: insert, search, delete, list.

This layer sits between the FastAPI routes and the database.
Routes call store functions; store functions call the DB.
No SQL lives in main.py — all of it is here.

Key concept — pgvector similarity search:

    SELECT *, 1 - (embedding <=> query_vec) AS score
    FROM documents
    ORDER BY embedding <=> query_vec
    LIMIT k;

    <=>  is the cosine distance operator (0 = identical, 2 = opposite)
    1 - distance converts to cosine similarity (1 = identical, -1 = opposite)
    ORDER BY distance ASC gives most similar first
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from database import get_connection


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class Document:
    """A stored document with its embedding."""
    id: int
    content: str
    embedding: list[float]
    source: str
    collection: str
    metadata: dict
    created_at: str

    def to_dict(self, include_embedding: bool = False) -> dict:
        d = {
            "id":         self.id,
            "content":    self.content,
            "source":     self.source,
            "collection": self.collection,
            "metadata":   self.metadata,
            "created_at": str(self.created_at),
        }
        if include_embedding:
            d["embedding"] = self.embedding
        return d


@dataclass
class SearchResult:
    """A single result from a similarity search."""
    document: Document
    score: float          # cosine similarity — 1.0 = identical, 0.0 = unrelated

    def to_dict(self, include_embedding: bool = False) -> dict:
        return {
            **self.document.to_dict(include_embedding=include_embedding),
            "score": round(self.score, 6),
        }


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _row_to_document(row) -> Document:
    """Convert a psycopg2 RealDictRow to a Document."""
    return Document(
        id=row["id"],
        content=row["content"],
        # pgvector returns embeddings as a string "[0.1,0.2,...]"
        # when not using the vector type natively — parse it
        embedding=_parse_vector(row["embedding"]),
        source=row["source"],
        collection=row["collection"],
        metadata=row["metadata"] if isinstance(row["metadata"], dict)
                 else json.loads(row["metadata"]),
        created_at=row["created_at"],
    )


def _parse_vector(val) -> list[float]:
    """
    Parse pgvector output to a Python list.
    pgvector returns vectors as "[0.1,0.2,0.3]" strings.
    """
    if val is None:
        return []
    if isinstance(val, list):
        return val
    # String format: "[0.1,0.2,0.3]"
    return [float(x) for x in str(val).strip("[]").split(",")]


def _format_vector(embedding: list[float]) -> str:
    """
    Format a Python list as pgvector literal string.
    pgvector accepts: '[0.1,0.2,0.3]'
    """
    return "[" + ",".join(str(x) for x in embedding) + "]"


# ------------------------------------------------------------------
# Insert
# ------------------------------------------------------------------

def insert_document(
    content: str,
    embedding: list[float],
    source: str = "",
    collection: str = "default",
    metadata: dict | None = None,
) -> Document:
    """
    Insert a single document with its embedding.
    Returns the inserted document including its generated ID.
    """
    sql = """
        INSERT INTO documents (content, embedding, source, collection, metadata)
        VALUES (%s, %s::vector, %s, %s, %s)
        RETURNING *
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                content,
                _format_vector(embedding),
                source,
                collection,
                json.dumps(metadata or {}),
            ))
            row = cur.fetchone()
        conn.commit()
    return _row_to_document(row)


def insert_batch(
    documents: list[dict],
) -> list[Document]:
    """
    Insert multiple documents in a single transaction.

    Each dict in `documents` must have:
        content    : str
        embedding  : list[float]
        source     : str (optional)
        collection : str (optional, default 'default')
        metadata   : dict (optional)

    Using executemany with a single transaction is significantly
    faster than individual inserts — one round-trip instead of N.
    """
    if not documents:
        return []

    sql = """
        INSERT INTO documents (content, embedding, source, collection, metadata)
        VALUES (%s, %s::vector, %s, %s, %s)
        RETURNING *
    """
    rows_params = [
        (
            doc["content"],
            _format_vector(doc["embedding"]),
            doc.get("source", ""),
            doc.get("collection", "default"),
            json.dumps(doc.get("metadata", {})),
        )
        for doc in documents
    ]

    inserted = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for params in rows_params:
                cur.execute(sql, params)
                inserted.append(cur.fetchone())
        conn.commit()

    return [_row_to_document(row) for row in inserted]


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

def search(
    query_embedding: list[float],
    k: int = 5,
    collection: str | None = None,
    source: str | None = None,
    min_score: float = 0.0,
) -> list[SearchResult]:
    """
    Find the k most similar documents to a query embedding.

    Uses cosine similarity via pgvector's <=> operator.
    Optionally filters by collection and/or source before searching.

    Parameters:
        query_embedding : vector to search with
        k               : number of results to return
        collection      : filter to this collection only
        source          : filter to this source only
        min_score       : minimum cosine similarity (0.0 = return all)

    The query uses:
        ORDER BY embedding <=> query_vec   ← sort by cosine DISTANCE (asc)
        1 - (embedding <=> query_vec)      ← convert to similarity (desc)

    Filtering before the vector search (WHERE collection = ...)
    is critical for performance — pgvector can use the HNSW index
    more efficiently when the candidate set is smaller.
    """
    vec_str = _format_vector(query_embedding)

    # Build WHERE clause dynamically based on filters
    conditions = []
    params: list = [vec_str]

    if collection:
        conditions.append(f"collection = %s")
        params.append(collection)

    if source:
        conditions.append(f"source = %s")
        params.append(source)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Append remaining params in order
    params.extend([vec_str, k])

    sql = f"""
        SELECT
            *,
            1 - (embedding <=> %s::vector) AS similarity_score
        FROM documents
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        score = float(row["similarity_score"])
        if score >= min_score:
            # Build Document without the similarity_score field
            doc_row = {k: v for k, v in row.items() if k != "similarity_score"}
            results.append(SearchResult(
                document=_row_to_document(doc_row),
                score=score,
            ))

    return results


# ------------------------------------------------------------------
# Get / Delete
# ------------------------------------------------------------------

def get_document(doc_id: int) -> Document | None:
    """Retrieve a single document by ID. Returns None if not found."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
            row = cur.fetchone()
    return _row_to_document(row) if row else None


def delete_document(doc_id: int) -> bool:
    """Delete a document by ID. Returns True if deleted, False if not found."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM documents WHERE id = %s RETURNING id", (doc_id,)
            )
            deleted = cur.fetchone()
        conn.commit()
    return deleted is not None


def delete_collection(collection: str) -> int:
    """
    Delete all documents in a collection.
    Returns the number of documents deleted.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM documents WHERE collection = %s", (collection,)
            )
            count = cur.rowcount
        conn.commit()
    return count


# ------------------------------------------------------------------
# List / Stats
# ------------------------------------------------------------------

def list_collections() -> list[dict]:
    """
    List all collections with document counts and creation dates.
    """
    sql = """
        SELECT
            collection,
            COUNT(*)        AS document_count,
            MIN(created_at) AS created_at,
            MAX(created_at) AS updated_at
        FROM documents
        GROUP BY collection
        ORDER BY document_count DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [
        {
            "collection":     row["collection"],
            "document_count": row["document_count"],
            "created_at":     str(row["created_at"]),
            "updated_at":     str(row["updated_at"]),
        }
        for row in rows
    ]


def get_stats() -> dict:
    """Return total document count and collection breakdown."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM documents")
            total = cur.fetchone()["total"]
    return {
        "total_documents": total,
        "collections":     list_collections(),
    }
