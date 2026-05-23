"""
Resume Scoring API (Dockerized) — Main Application

Identical routes to Project 4 but backed by PostgreSQL instead of SQLite.

Key differences from Project 4:
- psycopg2 uses %s placeholders instead of ?
- Skills stored as JSONB in PostgreSQL (native array, not JSON string)
- json.loads() not needed on read — psycopg2 deserializes JSONB automatically
- Cursor used as context manager: `with conn.cursor() as cur`
- Explicit conn.commit() required (psycopg2 defaults to manual commit mode)

Routes:
    GET  /health           → health check
    POST /scores           → score a resume
    GET  /scores           → list scores (paginated, filterable)
    GET  /scores/{id}      → get a single score
    DELETE /scores/{id}    → delete a score
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Query, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from database import get_connection, init_db
from models import (
    ScoreRequest, ScoreResponse, ScoreListResponse,
    ScoreListItem, DeleteResponse, HealthResponse,
)
from scorer import ResumeScorer


# ------------------------------------------------------------------
# App lifecycle
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Resume Scoring API",
    description="Score resumes against job descriptions. Backed by PostgreSQL.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scorer = ResumeScorer()


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def row_to_score_response(row) -> ScoreResponse:
    """
    Convert a psycopg2 RealDictRow to ScoreResponse.

    Note: PostgreSQL JSONB columns are automatically deserialized
    to Python lists by psycopg2 — no json.loads() needed.
    This is different from Project 4 where skills were stored as
    JSON strings in SQLite and required manual json.loads().
    """
    return ScoreResponse(
        id=row["id"],
        candidate_name=row["candidate_name"],
        job_title=row["job_title"],
        score=row["score"],
        matched_skills=row["matched_skills"],   # already a list
        missing_skills=row["missing_skills"],   # already a list
        recommendation=row["recommendation"],
        resume_snippet=row["resume_snippet"],
        created_at=str(row["created_at"]),
    )


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Public endpoint — no auth required."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM scores")
            total = cur.fetchone()["total"]
    return HealthResponse(status="ok", total_scores=total)


@app.post(
    "/scores",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scores"],
)
def create_score(
    body: ScoreRequest,
    _: str = Security(verify_api_key),
):
    """Score a resume against a job description and persist the result."""
    result = scorer.score(body.resume_text, body.job_description)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scores
                   (candidate_name, job_title, score, matched_skills,
                    missing_skills, recommendation, resume_snippet)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (
                    body.candidate_name,
                    body.job_title,
                    result.score,
                    json.dumps(result.matched_skills),   # psycopg2 accepts JSON string for JSONB
                    json.dumps(result.missing_skills),
                    result.recommendation,
                    result.resume_snippet,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return row_to_score_response(row)


@app.get("/scores", response_model=ScoreListResponse, tags=["Scores"])
def list_scores(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_score: float | None = Query(default=None, ge=0, le=100),
    _: str = Security(verify_api_key),
):
    """List all scores with pagination and optional minimum score filter."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if min_score is not None:
                cur.execute("SELECT COUNT(*) AS total FROM scores WHERE score >= %s", (min_score,))
                total = cur.fetchone()["total"]
                cur.execute(
                    """SELECT id, candidate_name, job_title, score, recommendation, created_at
                       FROM scores WHERE score >= %s
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (min_score, limit, offset),
                )
            else:
                cur.execute("SELECT COUNT(*) AS total FROM scores")
                total = cur.fetchone()["total"]
                cur.execute(
                    """SELECT id, candidate_name, job_title, score, recommendation, created_at
                       FROM scores ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
            rows = cur.fetchall()

    return ScoreListResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=[
            ScoreListItem(
                id=r["id"],
                candidate_name=r["candidate_name"],
                job_title=r["job_title"],
                score=r["score"],
                recommendation=r["recommendation"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ],
    )


@app.get("/scores/{score_id}", response_model=ScoreResponse, tags=["Scores"])
def get_score(
    score_id: int,
    _: str = Security(verify_api_key),
):
    """Retrieve a single score result by ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM scores WHERE id = %s", (score_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Score with id {score_id} not found.",
        )
    return row_to_score_response(row)


@app.delete("/scores/{score_id}", response_model=DeleteResponse, tags=["Scores"])
def delete_score(
    score_id: int,
    _: str = Security(verify_api_key),
):
    """Delete a score result by ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM scores WHERE id = %s", (score_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Score with id {score_id} not found.",
                )
            cur.execute("DELETE FROM scores WHERE id = %s", (score_id,))
        conn.commit()

    return DeleteResponse(message="Score deleted successfully.", id=score_id)
