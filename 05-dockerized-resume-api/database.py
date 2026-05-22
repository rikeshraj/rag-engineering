"""
Database

PostgreSQL connection using psycopg2.
Connection string is loaded from the DATABASE_URL environment variable.

Differences from Project 4 (SQLite):
- Uses psycopg2 instead of sqlite3
- Connection string via DATABASE_URL env var instead of a file path
- %s placeholders instead of ? for parameterized queries
- RealDictCursor so columns are accessible by name (like sqlite3.Row)
- Connection pooling handled by psycopg2 directly
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    id              SERIAL PRIMARY KEY,
    candidate_name  TEXT NOT NULL,
    job_title       TEXT NOT NULL DEFAULT '',
    score           REAL NOT NULL,
    matched_skills  JSONB NOT NULL DEFAULT '[]',
    missing_skills  JSONB NOT NULL DEFAULT '[]',
    recommendation  TEXT NOT NULL,
    resume_snippet  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scores_created_at ON scores(created_at);
CREATE INDEX IF NOT EXISTS idx_scores_score       ON scores(score);
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
    Return a psycopg2 connection with RealDictCursor as default cursor.
    RealDictCursor makes rows accessible by column name: row["score"]
    instead of row[2] — same behaviour as sqlite3.Row in Project 4.
    """
    conn = psycopg2.connect(
        get_database_url(),
        cursor_factory=RealDictCursor,
    )
    return conn


def init_db() -> None:
    """Create tables and indexes if they don't exist. Safe to call on every startup."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
