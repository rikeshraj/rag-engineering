"""
Database Schema

Creates all tables and indexes for the Employee Analytics DB.
Run this once to initialize the database.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("employees.db")

SCHEMA = """
-- Locations table
CREATE TABLE IF NOT EXISTS locations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    city      TEXT NOT NULL,
    country   TEXT NOT NULL DEFAULT 'US'
);

-- Departments table
CREATE TABLE IF NOT EXISTS departments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    location_id   INTEGER REFERENCES locations(id)
);

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    email            TEXT UNIQUE NOT NULL,
    job_title        TEXT NOT NULL,
    department_id    INTEGER REFERENCES departments(id),
    manager_id       INTEGER REFERENCES employees(id),
    salary           REAL NOT NULL,
    hire_date        TEXT NOT NULL,   -- stored as YYYY-MM-DD
    is_remote        INTEGER DEFAULT 0  -- 0=false, 1=true (SQLite has no BOOL)
);

-- Performance reviews table
CREATE TABLE IF NOT EXISTS performance_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id   INTEGER NOT NULL REFERENCES employees(id),
    review_date   TEXT NOT NULL,
    score         REAL NOT NULL CHECK(score BETWEEN 1.0 AND 5.0),
    reviewer_id   INTEGER REFERENCES employees(id),
    notes         TEXT
);

-- Indexes for frequently queried columns
CREATE INDEX IF NOT EXISTS idx_employees_department  ON employees(department_id);
CREATE INDEX IF NOT EXISTS idx_employees_manager     ON employees(manager_id);
CREATE INDEX IF NOT EXISTS idx_employees_hire_date   ON employees(hire_date);
CREATE INDEX IF NOT EXISTS idx_reviews_employee      ON performance_reviews(employee_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date          ON performance_reviews(review_date);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Return a database connection with foreign key enforcement enabled.
    Row factory set to sqlite3.Row so columns are accessible by name.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables and indexes if they don't exist."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialized at '{db_path}'")


if __name__ == "__main__":
    init_db()
