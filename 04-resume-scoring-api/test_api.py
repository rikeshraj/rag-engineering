"""
Optional tests for Resume Scoring API.

Run with:
    pip install pytest httpx
    pytest tests/ -v
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

# Set env vars before importing app
os.environ["API_KEY"] = "test-key-123"

# Point DB to a temp test file
import database
database.DB_PATH = database.Path("test_scores.db")

from main import app
from database import init_db

# Initialize DB before any tests run
init_db(database.DB_PATH)

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key-123"}

SAMPLE_RESUME = """
Jane Smith — Senior Python Engineer
jane@email.com | San Francisco, CA

5 years of experience building backend systems.

Skills: Python, FastAPI, PostgreSQL, Docker, AWS, Redis, Git

Experience:
Senior Engineer - Acme Corp (2021-Present)
- Built REST APIs using FastAPI serving 1M requests/day
- Deployed services on AWS using Docker and Kubernetes

Education:
B.S. Computer Science - Stanford University, 2019
"""

SAMPLE_JD = """
We are looking for a Senior Python Engineer with:
- 4+ years of experience
- Strong Python and FastAPI skills
- Experience with PostgreSQL and Docker
- AWS knowledge preferred
- Experience with REST APIs
- B.S. in Computer Science or related field
"""


class TestHealth:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "total_scores" in data

    def test_health_no_auth_required(self):
        response = client.get("/health")
        assert response.status_code == 200


class TestAuth:
    def test_missing_api_key(self):
        response = client.post("/scores", json={
            "candidate_name": "Test",
            "resume_text": "some resume",
            "job_description": "some jd",
        })
        assert response.status_code == 401

    def test_wrong_api_key(self):
        response = client.post(
            "/scores",
            json={"candidate_name": "Test", "resume_text": "resume", "job_description": "jd"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_valid_api_key(self):
        response = client.post(
            "/scores",
            json={
                "candidate_name": "Jane",
                "resume_text": SAMPLE_RESUME,
                "job_description": SAMPLE_JD,
            },
            headers=HEADERS,
        )
        assert response.status_code == 201


class TestCreateScore:
    def test_returns_score_fields(self):
        response = client.post(
            "/scores",
            json={
                "candidate_name": "Jane Smith",
                "job_title": "Senior Python Engineer",
                "resume_text": SAMPLE_RESUME,
                "job_description": SAMPLE_JD,
            },
            headers=HEADERS,
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "score" in data
        assert "matched_skills" in data
        assert "missing_skills" in data
        assert "recommendation" in data
        assert 0 <= data["score"] <= 100

    def test_score_is_higher_for_matching_resume(self):
        strong = client.post("/scores", json={
            "candidate_name": "Jane",
            "resume_text": SAMPLE_RESUME,
            "job_description": SAMPLE_JD,
        }, headers=HEADERS).json()

        weak = client.post("/scores", json={
            "candidate_name": "Bob",
            "resume_text": "I am a chef with 10 years of culinary experience.",
            "job_description": SAMPLE_JD,
        }, headers=HEADERS).json()

        assert strong["score"] > weak["score"]

    def test_invalid_request_missing_fields(self):
        response = client.post(
            "/scores",
            json={"candidate_name": "Jane"},
            headers=HEADERS,
        )
        assert response.status_code == 422

    def test_resume_snippet_truncated(self):
        long_resume = "Python " * 500
        response = client.post("/scores", json={
            "candidate_name": "Test",
            "resume_text": long_resume,
            "job_description": SAMPLE_JD,
        }, headers=HEADERS)
        data = response.json()
        assert len(data["resume_snippet"]) <= 310


class TestListScores:
    def test_list_returns_results(self):
        response = client.get("/scores", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_pagination(self):
        response = client.get("/scores?limit=2&offset=0", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 2

    def test_min_score_filter(self):
        response = client.get("/scores?min_score=90", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        for r in data["results"]:
            assert r["score"] >= 90


class TestGetScore:
    def test_get_existing_score(self):
        created = client.post("/scores", json={
            "candidate_name": "Test User",
            "resume_text": SAMPLE_RESUME,
            "job_description": SAMPLE_JD,
        }, headers=HEADERS).json()

        response = client.get(f"/scores/{created['id']}", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_nonexistent_score(self):
        response = client.get("/scores/999999", headers=HEADERS)
        assert response.status_code == 404


class TestDeleteScore:
    def test_delete_existing_score(self):
        created = client.post("/scores", json={
            "candidate_name": "Delete Me",
            "resume_text": SAMPLE_RESUME,
            "job_description": SAMPLE_JD,
        }, headers=HEADERS).json()

        response = client.delete(f"/scores/{created['id']}", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

        get_response = client.get(f"/scores/{created['id']}", headers=HEADERS)
        assert get_response.status_code == 404

    def test_delete_nonexistent_score(self):
        response = client.delete("/scores/999999", headers=HEADERS)
        assert response.status_code == 404
