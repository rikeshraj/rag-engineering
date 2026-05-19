"""
Resume Scoring API — Main Application

Routes:
    GET  /health           → health check + total scores count
    POST /scores           → score a resume against a job description
    GET  /scores           → list all scores (paginated, filterable)
    GET  /scores/{id}      → get a single score result
    DELETE /scores/{id}    → delete a score result
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Query, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from database import get_connection, init_db, DB_PATH
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
    """Initialize DB on startup."""
    init_db()
    yield


app = FastAPI(
    title="Resume Scoring API",
    description="Score resumes against job descriptions using keyword matching.",
    version="1.0.0",
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
    """Convert a sqlite3.Row to a ScoreResponse model."""
    return ScoreResponse(
        id=row["id"],
        candidate_name=row["candidate_name"],
        job_title=row["job_title"],
        score=row["score"],
        matched_skills=json.loads(row["matched_skills"]),
        missing_skills=json.loads(row["missing_skills"]),
        recommendation=row["recommendation"],
        resume_snippet=row["resume_snippet"],
        created_at=row["created_at"],
    )


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Public endpoint — no auth required."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
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
    """
    Score a resume against a job description.

    - Validates request body via Pydantic
    - Runs keyword-based scoring
    - Persists result to SQLite
    - Returns full ScoreResponse
    """
    result = scorer.score(body.resume_text, body.job_description)

    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO scores
               (candidate_name, job_title, score, matched_skills,
                missing_skills, recommendation, resume_snippet)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                body.candidate_name,
                body.job_title,
                result.score,
                json.dumps(result.matched_skills),
                json.dumps(result.missing_skills),
                result.recommendation,
                result.resume_snippet,
            ),
        )
        score_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM scores WHERE id = ?", (score_id,)
        ).fetchone()

    return row_to_score_response(row)


@app.get("/scores", response_model=ScoreListResponse, tags=["Scores"])
def list_scores(
    limit: int  = Query(default=10,  ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0,   ge=0,          description="Pagination offset"),
    min_score: float | None = Query(default=None, ge=0, le=100, description="Filter by minimum score"),
    _: str = Security(verify_api_key),
):
    """
    List all scores with pagination and optional score filter.

    Query params:
        limit      — results per page (1-100, default 10)
        offset     — pagination offset (default 0)
        min_score  — only return scores >= this value
    """
    with get_connection() as conn:
        if min_score is not None:
            total = conn.execute(
                "SELECT COUNT(*) FROM scores WHERE score >= ?", (min_score,)
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT id, candidate_name, job_title, score, recommendation, created_at
                   FROM scores WHERE score >= ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (min_score, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
            rows = conn.execute(
                """SELECT id, candidate_name, job_title, score, recommendation, created_at
                   FROM scores ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()

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
                created_at=r["created_at"],
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
        row = conn.execute(
            "SELECT * FROM scores WHERE id = ?", (score_id,)
        ).fetchone()

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
        row = conn.execute(
            "SELECT id FROM scores WHERE id = ?", (score_id,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Score with id {score_id} not found.",
            )

        conn.execute("DELETE FROM scores WHERE id = ?", (score_id,))

    return DeleteResponse(message="Score deleted successfully.", id=score_id)
