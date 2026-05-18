# Resume Scoring API

A REST API built with FastAPI that scores resumes against job descriptions using keyword matching. Stores all results in SQLite and protects every endpoint with API key authentication.

## What it does

- Accepts a resume and job description, returns a match score (0–100)
- Breaks the score down into matched skills, missing skills, and a recommendation
- Persists every result to SQLite for later retrieval
- Full CRUD — create, list, get, and delete scores
- API key auth on all routes except `/health`
- Auto-generated Swagger docs at `/docs`

## How scoring works

```
Final Score = (Skills × 60%) + (Experience × 25%) + (Education × 15%)
```

| Component | Weight | Method |
|---|---|---|
| Skills | 60% | % of JD skills found in resume |
| Experience | 25% | Experience keywords + years mentioned |
| Education | 15% | Degree keywords from JD found in resume |

## Setup

```bash
git clone https://github.com/yourname/rag-engineering
cd rag-engineering/04-resume-scoring-api

pip install -r requirements.txt

# Create your .env file
cp .env.example .env
# Open .env and set: API_KEY=your-secret-key

# Start the server
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## API Endpoints

| Method | Endpoint | Auth | Status | Description |
|---|---|---|---|---|
| GET | `/health` | ❌ | 200 | Health check + total score count |
| POST | `/scores` | ✅ | 201 | Score a resume against a JD |
| GET | `/scores` | ✅ | 200 | List scores (paginated, filterable) |
| GET | `/scores/{id}` | ✅ | 200 | Get one score by ID |
| DELETE | `/scores/{id}` | ✅ | 200 | Delete a score by ID |

---

## Usage

### Score a resume

```bash
curl -X POST http://localhost:8000/scores \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_name": "Jane Smith",
    "job_title": "Senior Python Engineer",
    "resume_text": "Python developer with 5 years experience in FastAPI, PostgreSQL, Docker...",
    "job_description": "Looking for a Python engineer with FastAPI, Docker, and SQL experience..."
  }'
```

**Response:**
```json
{
  "id": 1,
  "candidate_name": "Jane Smith",
  "job_title": "Senior Python Engineer",
  "score": 77.5,
  "matched_skills": ["python", "fastapi", "postgresql", "docker"],
  "missing_skills": ["redis", "kubernetes"],
  "recommendation": "Good match — consider for interview",
  "resume_snippet": "Python developer with 5 years experience...",
  "created_at": "2024-01-15 10:30:00"
}
```

### List scores

```bash
# All scores, 10 per page
curl http://localhost:8000/scores \
  -H "X-API-Key: your-secret-key"

# Filter by minimum score, custom pagination
curl "http://localhost:8000/scores?min_score=70&limit=5&offset=0" \
  -H "X-API-Key: your-secret-key"
```

### Get a score by ID

```bash
curl http://localhost:8000/scores/1 \
  -H "X-API-Key: your-secret-key"
```

### Delete a score

```bash
curl -X DELETE http://localhost:8000/scores/1 \
  -H "X-API-Key: your-secret-key"
```

---

## Project Structure

```
04-resume-scoring-api/
├── main.py          # FastAPI app — all routes
├── scorer.py        # Keyword matching + scoring logic
├── models.py        # Pydantic request/response models
├── auth.py          # API key authentication dependency
├── database.py      # SQLite setup + connection helper
├── .env.example     # Environment variable template
├── requirements.txt
└── README.md
```

### How the files connect

```
Request
  ↓
main.py          ← routes, ties everything together
  ├── auth.py    ← verify API key before route runs
  ├── models.py  ← validate request body, serialize response
  ├── scorer.py  ← compute score from resume + JD text
  └── database.py ← persist and retrieve results
```

---

## Key Concepts Used

| Concept | Where |
|---|---|
| FastAPI routing | `main.py` — all 5 routes |
| Pydantic v2 validation | `models.py` — Field constraints, auto 422 on bad input |
| Dependency injection | `auth.py` — `Security(verify_api_key)` on each route |
| HTTP status codes | 201 Created, 401 Unauthorized, 404 Not Found, 422 Unprocessable |
| Query parameters | `GET /scores?limit=10&offset=0&min_score=70` |
| Path parameters | `GET /scores/{id}`, `DELETE /scores/{id}` |
| SQLite + JSON | Skills stored as JSON strings, deserialized on read |
| Environment variables | `API_KEY` loaded from `.env` via `python-dotenv` |
| Lifespan events | DB initialized on app startup via `@asynccontextmanager` |
| Regex word boundaries | `\b` in scorer prevents partial skill matches |

---

## Recommendation Thresholds

| Score | Recommendation |
|---|---|
| ≥ 80 | Strong match — recommend for interview |
| 60–79 | Good match — consider for interview |
| 40–59 | Partial match — review manually |
| < 40 | Weak match — likely not suitable |

---

## What's next

Project 5 takes this API and:
- Replaces SQLite with **PostgreSQL** running in Docker
- Adds a **Dockerfile** and **docker-compose.yml**
- Adds a **Makefile** for one-command operations
- Runs the full stack with `docker-compose up`
