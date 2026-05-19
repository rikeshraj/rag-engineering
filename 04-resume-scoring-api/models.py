"""
Models

Pydantic models for all request and response shapes.
FastAPI uses these to validate incoming data and serialize responses.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request models (what the client sends)
# ------------------------------------------------------------------

class ScoreRequest(BaseModel):
    """Body for POST /scores"""
    candidate_name: str = Field(
        min_length=1,
        max_length=100,
        description="Full name of the candidate",
    )
    resume_text: str = Field(
        min_length=10,
        description="Plain text content of the resume",
    )
    job_description: str = Field(
        min_length=10,
        description="Plain text job description to match against",
    )
    job_title: str = Field(
        default="",
        max_length=100,
        description="Optional job title for reference",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "candidate_name": "Jane Smith",
                "job_title": "Senior Python Engineer",
                "resume_text": "Python developer with 5 years experience in FastAPI, PostgreSQL, Docker...",
                "job_description": "We need a Python engineer with FastAPI, Docker, and SQL experience...",
            }
        }
    }


# ------------------------------------------------------------------
# Response models (what the API returns)
# ------------------------------------------------------------------

class ScoreResponse(BaseModel):
    """Response for POST /scores and GET /scores/{id}"""
    id: int
    candidate_name: str
    job_title: str
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation: str
    resume_snippet: str
    created_at: str


class ScoreListItem(BaseModel):
    """Condensed item used in GET /scores list"""
    id: int
    candidate_name: str
    job_title: str
    score: float
    recommendation: str
    created_at: str


class ScoreListResponse(BaseModel):
    """Paginated list of scores"""
    total: int
    limit: int
    offset: int
    results: list[ScoreListItem]


class DeleteResponse(BaseModel):
    """Response for DELETE /scores/{id}"""
    message: str
    id: int


class HealthResponse(BaseModel):
    """Response for GET /health"""
    status: str
    total_scores: int
