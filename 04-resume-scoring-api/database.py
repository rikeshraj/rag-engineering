"""
Database

SQLite setup using sqlite3 stdlib.
Stores all score results so they can be retrieved later.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("scores.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name  TEXT NOT NULL,
    job_title       TEXT NOT NULL DEFAULT '',
    score           REAL NOT NULL,
    matched_skills  TEXT NOT NULL DEFAULT '[]',
    missing_skills  TEXT NOT NULL DEFAULT '[]',
    recommendation  TEXT NOT NULL,
    resume_snippet  TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scores_created_at ON scores(created_at);
CREATE INDEX IF NOT EXISTS idx_scores_score       ON scores(score);
"""


def get_connection(db_path=None) -> sqlite3.Connection:
    """Always read module-level DB_PATH so tests can override it."""
    import database as _db
    path = db_path if db_path is not None else _db.DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path=None) -> None:
    import database as _db
    path = db_path if db_path is not None else _db.DB_PATH
    with get_connection(path) as conn:
        conn.executescript(SCHEMA)
