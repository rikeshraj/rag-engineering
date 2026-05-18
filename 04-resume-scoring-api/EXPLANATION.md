# Resume Scoring API — File-by-File Breakdown

A complete explanation of every file in the project, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
04-resume-scoring-api/
├── main.py          # FastAPI app + all routes
├── scorer.py        # Keyword matching + scoring logic
├── models.py        # Pydantic request/response models
├── auth.py          # API key verification
├── database.py      # SQLite setup + connection helper
├── .env.example     # Environment variable template
├── requirements.txt
├── README.md
└── tests/
    └── test_api.py
```

---

## `database.py`

### What it does
Sets up the SQLite database — creates the table, defines indexes, and provides a single `get_connection()` function that every other file uses to talk to the database.

### The schema

```sql
CREATE TABLE IF NOT EXISTS scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name  TEXT NOT NULL,
    job_title       TEXT NOT NULL DEFAULT '',
    score           REAL NOT NULL,
    matched_skills  TEXT NOT NULL DEFAULT '[]',   -- JSON string
    missing_skills  TEXT NOT NULL DEFAULT '[]',   -- JSON string
    recommendation  TEXT NOT NULL,
    resume_snippet  TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Key decisions

**Why SQLite?**
No server to set up, no credentials to manage, no Docker dependency for the DB layer. The database is a single file (`scores.db`) that lives next to the code. For a portfolio project and early-stage API this is the right call — PostgreSQL comes in Project 5.

**Why store `matched_skills` and `missing_skills` as JSON strings?**
SQLite has no native array type. The options were: a separate junction table (overkill for this use case), or serialize as JSON and deserialize on read. JSON was chosen because the skills list is always read and written together — never queried individually — so there's no benefit to normalizing it into rows.

**`row_factory = sqlite3.Row`**
Without this, every query result is a plain tuple and you access columns by index: `row[3]`. With it, columns are accessible by name: `row["score"]`. This is set once in `get_connection()` so every query in the codebase gets this behavior automatically.

**`PRAGMA foreign_keys = ON`**
SQLite does not enforce foreign key constraints by default — it ignores them unless you explicitly turn them on per connection. This line ensures referential integrity is always enforced.

**`PRAGMA journal_mode = WAL`**
WAL (Write-Ahead Logging) is a SQLite journaling mode that allows multiple simultaneous readers while a write is in progress. The default mode locks the entire database during writes, which causes issues when the API receives concurrent requests. WAL eliminates that bottleneck.

**`init_db()`**
Uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` so it's safe to call on every startup — it only creates things that don't already exist. This means no separate migration step is needed.

---

## `models.py`

### What it does
Defines all Pydantic models for request validation and response serialization. FastAPI uses these to automatically validate incoming JSON, reject bad requests with a 422 error, and serialize outgoing responses.

### Models

| Model | Used for |
|---|---|
| `ScoreRequest` | Body of `POST /scores` |
| `ScoreResponse` | Response from `POST /scores` and `GET /scores/{id}` |
| `ScoreListItem` | Single item inside `GET /scores` list |
| `ScoreListResponse` | Full response from `GET /scores` |
| `DeleteResponse` | Response from `DELETE /scores/{id}` |
| `HealthResponse` | Response from `GET /health` |

### Key decisions

**Why separate models for list vs detail?**
`ScoreListItem` is a condensed version of `ScoreResponse` — it omits `matched_skills`, `missing_skills`, and `resume_snippet` because listing 100 scores with full skill arrays would be wasteful. The list view only needs what's necessary to identify and compare results. The detail view (`GET /scores/{id}`) returns everything.

**Pydantic field validation**
```python
candidate_name: str = Field(min_length=1, max_length=100)
resume_text: str = Field(min_length=10)
job_description: str = Field(min_length=10)
```
These constraints are enforced automatically by FastAPI. If a client sends an empty name or a one-word resume, the API returns a 422 with a clear error message — no manual validation code needed in the route handlers.

**`model_config` with `json_schema_extra`**
The `example` block inside `ScoreRequest` populates the Swagger docs at `/docs` with a pre-filled example request. This makes the API self-documenting — anyone visiting `/docs` can test it immediately without reading the README.

**Why Pydantic v2?**
Pydantic v2 (released 2023) is significantly faster than v1 and is now the standard. The key difference in syntax is `model_config` instead of the old inner `Config` class, and `model_dump()` instead of `dict()`.

---

## `auth.py`

### What it does
Implements API key authentication using FastAPI's dependency injection system. Any route that includes `Security(verify_api_key)` as a parameter is automatically protected — FastAPI calls `verify_api_key` before the route handler runs.

### How it works

```
Client sends request with header: X-API-Key: your-key
                    ↓
FastAPI sees Security(verify_api_key) on the route
                    ↓
verify_api_key() is called automatically
                    ↓
Key matches? → route handler runs
Key missing or wrong? → 401 returned, handler never called
```

### Key decisions

**`APIKeyHeader` vs manual header parsing**
FastAPI's `APIKeyHeader` is a built-in security utility that:
- Extracts the header value automatically
- Integrates with the OpenAPI schema so `/docs` shows a lock icon and an "Authorize" button
- Handles the `auto_error=False` flag so we can return a custom error message instead of FastAPI's default

**`auto_error=False`**
By default, `APIKeyHeader` raises a generic 403 if the header is missing. Setting `auto_error=False` lets `verify_api_key` receive `None` when the header is absent, so we can raise a more descriptive 401 with a helpful message.

**401 vs 403**
- 401 Unauthorized = "I don't know who you are" (missing or invalid credentials)
- 403 Forbidden = "I know who you are, but you're not allowed"

Both cases here (missing key and wrong key) return 401 because the client has not proven their identity.

**`get_api_key()` raises on startup if env var is missing**
Rather than silently returning `None` and failing on the first request, `get_api_key()` raises a `RuntimeError` immediately if `API_KEY` is not set. This surfaces the configuration error at startup rather than hiding it.

**Why not JWT?**
JWT is appropriate for user-facing apps where tokens carry identity claims (user ID, roles, expiry). For server-to-server API calls — which is the use case here — a static API key is simpler, equally secure, and has no token refresh complexity.

---

## `scorer.py`

### What it does
The core business logic. Takes a resume and a job description as plain text strings and returns a `ScoreResult` with a numeric score, matched skills, missing skills, and a recommendation.

### Scoring formula

```
Final Score = (skill_score × 0.60) + (exp_score × 0.25) + (edu_score × 0.15)
```

| Component | Weight | How calculated |
|---|---|---|
| Skills | 60% | % of JD skills found in resume |
| Experience | 25% | % of experience signals matched + year bonus |
| Education | 15% | % of education keywords matched |

### Key decisions

**Why keyword matching instead of embeddings?**
This project is about learning REST API patterns, not AI. Keyword matching is transparent, fast, deterministic, and requires no external API calls or models. Embedding-based semantic matching (the RAG way) comes later in the curriculum.

**`re.search` with `\b` word boundaries**
```python
pattern = r"\b" + re.escape(skill) + r"\b"
```
`\b` is a word boundary anchor. Without it, searching for `"go"` would match inside `"postgresql"`, `"django"`, `"mongo"` — every word containing "go". The word boundary ensures we only match the whole word `"go"`.

`re.escape()` escapes special regex characters in skill names like `"c++"` — without it, the `+` would be interpreted as a regex quantifier and the pattern would fail.

**Neutral scores for missing JD signals**
```python
if not jd_signals:
    return 70.0  # neutral
```
If the JD doesn't mention any experience or education requirements, the candidate shouldn't be penalized for not matching signals that don't exist. A neutral 70.0 is used instead of 0.

**`ScoreResult` is a dataclass, not a Pydantic model**
`ScoreResult` is internal to the scorer — it never touches the API layer directly. Using a plain dataclass keeps the scorer independent of FastAPI and Pydantic. The conversion to `ScoreResponse` happens in `main.py`, keeping concerns separated.

**`_snippet()` — first 300 characters**
Stores a preview of the resume so results can be reviewed later without storing the full text. This is a privacy-conscious decision — the full resume isn't persisted, only a snippet.

---

## `main.py`

### What it does
The FastAPI application. Defines all routes, connects requests to the scorer and database, and handles errors.

### Routes

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| GET | `/health` | ❌ | 200 | System health + score count |
| POST | `/scores` | ✅ | 201 | Score a resume |
| GET | `/scores` | ✅ | 200 | List scores (paginated) |
| GET | `/scores/{id}` | ✅ | 200 | Get one score |
| DELETE | `/scores/{id}` | ✅ | 200 | Delete a score |

### Key decisions

**`lifespan` context manager instead of `@app.on_event`**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
```
`@app.on_event("startup")` is deprecated in newer FastAPI versions. `lifespan` is the modern replacement — everything before `yield` runs on startup, everything after runs on shutdown. Used here to initialize the database once when the server starts.

**`response_model` on every route**
```python
@app.post("/scores", response_model=ScoreResponse, status_code=201)
```
`response_model` tells FastAPI to:
1. Validate the response against the Pydantic model
2. Strip any extra fields not in the model (security benefit)
3. Auto-generate the correct response schema in `/docs`

**`status_code=201` on POST**
HTTP 201 Created is the correct status for a successful resource creation. The default is 200 OK. This is a REST convention — `GET` returns 200, `POST` that creates something returns 201.

**`_: str = Security(verify_api_key)` naming convention**
The underscore `_` is a Python convention for "I need this dependency to run but I don't use its return value in the function body." The auth check happens as a side effect — if it raises, the route doesn't run.

**`row_to_score_response()` helper**
Converting `sqlite3.Row` → `ScoreResponse` requires parsing the JSON skill arrays. This conversion is needed in two places (`POST` and `GET /{id}`), so it's extracted into a helper to avoid duplication.

**Pagination on `GET /scores`**
```
GET /scores?limit=10&offset=0&min_score=70
```
`limit` and `offset` are query parameters with validation (`ge=1, le=100`). The response includes `total` (total matching records) alongside the results so clients can calculate total pages. This is the standard pagination pattern for REST APIs.

**Why `json.dumps` / `json.loads` for skills?**
Skills are stored as JSON strings in SQLite (`'["python", "fastapi"]'`). On write: `json.dumps(list)` → string. On read: `json.loads(string)` → list. This round-trip is handled in `main.py` so `scorer.py` and `database.py` stay clean.

---

## `tests/test_api.py`

### What it does
Integration tests that test the full HTTP request/response cycle — auth, validation, CRUD operations, and error cases. Uses FastAPI's built-in `TestClient` which runs the app in-process without needing a real server.

### Key decisions

**Temp file database instead of in-memory**
```python
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TEST_DB = Path(_tmp.name)
```
SQLite `:memory:` databases don't persist across connections — each `get_connection()` call opens a fresh connection, so a new empty database appears every time. A temp file on disk persists across connections for the duration of the test session.

**Patching `database.DB_PATH` before importing `main`**
```python
import database
database.DB_PATH = TEST_DB   # patch first
from main import app          # then import
```
Order matters. `main.py` imports `database` at the top. If we imported `main` first, it would use the production `scores.db`. By patching `database.DB_PATH` before importing `main`, all subsequent `get_connection()` calls in the app use the test DB.

**`os.environ["API_KEY"] = "test-key"` before import**
Same reason — `auth.py` reads `API_KEY` from the environment. Setting it before import ensures `get_api_key()` doesn't raise a `RuntimeError` during test setup.

**Test classes group related tests**
Tests are organized into classes (`TestHealth`, `TestAuth`, `TestCreateScore`, etc.) rather than flat functions. This groups related tests visually and makes it easy to run a subset: `pytest tests/ -v -k TestAuth`.

**Each destructive test creates its own data**
`TestDeleteScore.test_delete_and_confirm_gone` creates a score, deletes it, then confirms it's gone — all in one test. This makes the test self-contained and independent of test execution order.

---

## `requirements.txt`

```
fastapi>=0.110.0     # web framework
uvicorn>=0.27.0      # ASGI server that runs FastAPI
pydantic>=2.0.0      # data validation (FastAPI dependency)
python-dotenv>=1.0.0 # loads .env file into os.environ

pytest>=7.0          # test runner (optional)
httpx>=0.27.0        # HTTP client required by FastAPI TestClient
```

**Why `uvicorn`?**
FastAPI is an ASGI framework — it needs an ASGI-compatible server to run. Uvicorn is the standard choice. `uvicorn main:app --reload` starts the server with hot-reload for development.

**Why `python-dotenv`?**
Loads variables from `.env` into `os.environ` at startup. Without it you'd have to set environment variables manually in your shell before running the server. With it, you just create a `.env` file and run normally.

---

## `.env.example`

```
API_KEY=your-secret-key-here
```

This file is committed to git. The actual `.env` file (with your real key) is in `.gitignore` and never committed. Anyone cloning the repo copies `.env.example` to `.env` and fills in their own values.

**Never commit `.env` to git.** API keys in git history are a serious security risk — even if you delete the file later, the key remains in the commit history and can be found by scanning tools.
