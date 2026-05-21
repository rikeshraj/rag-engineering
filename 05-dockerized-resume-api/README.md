# Dockerized Resume Scoring API

The Resume Scoring API from Project 4, upgraded with PostgreSQL and fully containerized with Docker Compose. One command gets the entire stack running.

## What changed from Project 4

| | Project 4 | Project 5 |
|---|---|---|
| Database | SQLite (file) | PostgreSQL 15 (container) |
| Driver | `sqlite3` stdlib | `psycopg2` |
| Skills storage | JSON string | JSONB (native Postgres type) |
| Deployment | `uvicorn main:app` | `docker-compose up` |
| Config | `.env` file | `.env` → Docker env vars |

## Setup

```bash
git clone https://github.com/yourname/rag-engineering
cd rag-engineering/05-dockerized-resume-api

# Create your .env file
cp .env.example .env
# Edit .env — set API_KEY and POSTGRES_PASSWORD

# Build and start everything
make up
# or: docker-compose up --build -d

# Check it's running
make health
# or: curl http://localhost:8000/health
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

## Common Commands

```bash
make up          # build + start all services (detached)
make down        # stop containers
make logs        # stream API logs
make logs-all    # stream all service logs
make shell       # open shell inside API container
make ps          # show running containers
make clean       # stop + wipe database volume
make test        # run tests inside container
make health      # hit /health endpoint
```

## Usage

```bash
# Score a resume
curl -X POST http://localhost:8000/scores \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_name": "Jane Smith",
    "job_title": "Senior Python Engineer",
    "resume_text": "Python developer with 5 years FastAPI, Docker, PostgreSQL...",
    "job_description": "Looking for Python engineer with FastAPI, Docker, SQL..."
  }'

# List scores
curl "http://localhost:8000/scores?limit=10&min_score=70" \
  -H "X-API-Key: your-secret-api-key-here"
```

## Project Structure

```
05-dockerized-resume-api/
├── main.py            # FastAPI app (PostgreSQL version)
├── database.py        # psycopg2 connection + schema
├── scorer.py          # Scoring logic (unchanged from Project 4)
├── models.py          # Pydantic models (unchanged from Project 4)
├── auth.py            # API key auth (unchanged from Project 4)
├── Dockerfile         # Multi-stage Docker image
├── docker-compose.yml # API + PostgreSQL services
├── Makefile           # Shortcut commands
├── requirements.txt
├── .env.example
└── README.md
```

## How it works

```
docker-compose up
      ↓
  ┌─────────────────────────────────────┐
  │  db (postgres:15)                   │
  │  • starts first (healthcheck)       │
  │  • data persists in named volume    │
  └──────────────┬──────────────────────┘
                 │ depends_on (healthy)
  ┌──────────────▼──────────────────────┐
  │  api (FastAPI + uvicorn)            │
  │  • builds from Dockerfile           │
  │  • connects via DATABASE_URL        │
  │  • init_db() runs on startup        │
  │  • port 8000 exposed to host        │
  └─────────────────────────────────────┘
```

## Key Docker concepts used

| Concept | Where |
|---|---|
| Multi-stage build | `Dockerfile` — separate builder and final stages |
| Non-root user | `Dockerfile` — `appuser` runs the process |
| Layer caching | `Dockerfile` — requirements copied before code |
| Named volumes | `docker-compose.yml` — `postgres_data` |
| Health checks | `docker-compose.yml` — `pg_isready` before API starts |
| `depends_on` with condition | `docker-compose.yml` — waits for DB to be healthy |
| env_file | `docker-compose.yml` — loads `.env` into containers |

