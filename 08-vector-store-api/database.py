"""
Database

PostgreSQL + pgvector setup.

pgvector adds a native `vector` column type to PostgreSQL.
It stores embeddings as arrays of floats and provides operators
for similarity search:
    <=>  cosine distance
    <->  euclidean distance
    <#>  negative inner product

We use cosine distance (<=>) because all embedding models return
unit-normalized vectors, making cosine similarity the standard metric.
"""

import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor


SCHEMA = """
-- Enable pgvector extension (must run once per database)
CREATE EXTENSION IF NOT EXISTS vector;

-- Main documents table
-- Each row is one chunk with its embedding and metadata
CREATE TABLE IF NOT EXISTS documents (
    id          SERIAL PRIMARY KEY,
    content     TEXT NOT NULL,
    embedding   vector(1536),          -- pgvector column, 1536-dim for OpenAI
    source      TEXT    NOT NULL DEFAULT '',
    collection  TEXT    NOT NULL DEFAULT 'default',
    metadata    JSONB   NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW index for fast approximate nearest neighbour search.
-- HNSW (Hierarchical Navigable Small World) builds a graph where
-- each vector is connected to its nearest neighbours. Search
-- traverses the graph rather than scanning every row.
--
-- vector_cosine_ops — tells pgvector to optimize for cosine distance.
-- Must match the operator used in queries (<=>) .
CREATE INDEX IF NOT EXISTS idx_documents_embedding
    ON documents USING hnsw (embedding vector_cosine_ops);

-- B-tree index on collection for filtering before vector search.
-- Without this, pgvector would scan all rows then filter — slow.
CREATE INDEX IF NOT EXISTS idx_documents_collection
    ON documents(collection);

-- B-tree index on source for filtering by document origin.
CREATE INDEX IF NOT EXISTS idx_documents_source
    ON documents(source);
"""


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it to your .env file."
        )
    return url


def get_connection():
    """
    Return a psycopg2 connection with RealDictCursor.
    RealDictCursor makes rows accessible by column name: row["content"]
    """
    conn = psycopg2.connect(
        get_database_url(),
        cursor_factory=RealDictCursor,
    )
    return conn


def init_db() -> None:
    """
    Create tables, indexes, and enable pgvector.
    Safe to call on every startup — all statements use IF NOT EXISTS.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
    print("Vector store initialized.")
