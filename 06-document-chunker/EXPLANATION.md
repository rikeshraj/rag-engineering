# Dockerized Resume Scoring API — File-by-File Breakdown

A complete explanation of every file in the project, what changed from Project 4, and the key decisions made.

---

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
├── README.md
└── tests/
    └── test_api.py
```

### What changed from Project 4

| File | Status | Change |
|---|---|---|
| `database.py` | 🔄 Rewritten | SQLite → PostgreSQL (psycopg2) |
| `main.py` | 🔄 Updated | `%s` placeholders, `RETURNING *`, cursor context managers |
| `scorer.py` | ✅ Unchanged | Scoring logic is DB-agnostic |
| `models.py` | ✅ Unchanged | Pydantic models are DB-agnostic |
| `auth.py` | ✅ Unchanged | Auth is DB-agnostic |
| `Dockerfile` | 🆕 New | Multi-stage build, non-root user |
| `docker-compose.yml` | 🆕 New | API + PostgreSQL services |
| `Makefile` | 🆕 New | Shortcut commands |

---

## `Dockerfile`

### What it does
Builds the Docker image for the FastAPI app in two stages — a builder stage that installs dependencies, and a final stage that runs the app.

### Multi-stage build

```dockerfile
# Stage 1: Builder — install dependencies
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final — copy installed packages, run app
FROM python:3.11-slim
COPY --from=builder /usr/local/lib/python3.11/site-packages ...
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Why two stages?**
The builder stage has pip, build tools, and cached package files — all needed to install packages but not to run them. The final stage copies only the installed packages, not the build tooling. Result: a smaller, cleaner image with less attack surface.

**Layer caching — why `requirements.txt` is copied first**
```dockerfile
COPY requirements.txt .   ← copied first
RUN pip install ...        ← cached until requirements.txt changes
COPY . .                   ← copied last
```
Docker builds in layers. If you change `main.py`, Docker only reruns `COPY . .` — the pip install layer is served from cache. If you copied everything at once, any code change would trigger a full reinstall. Separating requirements from code is the most impactful caching optimization in any Python Dockerfile.

**Non-root user**
```dockerfile
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
```
Running as root inside a container means a compromised process has root privileges — it could escape the container, write to host mounts, or modify system files. Running as an unprivileged `appuser` limits blast radius. This is a Docker security best practice.

**`--host 0.0.0.0`**
By default, uvicorn binds to `127.0.0.1` (localhost only). Inside a container, localhost is the container itself — not reachable from outside. `0.0.0.0` binds to all interfaces, making the port reachable through the container's network interface.

---

## `docker-compose.yml`

### What it does
Defines two services — `api` (FastAPI) and `db` (PostgreSQL) — and how they connect to each other.

### Service dependency with health checks

```yaml
api:
  depends_on:
    db:
      condition: service_healthy

db:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
    interval: 5s
    retries: 5
```

**Why `condition: service_healthy` instead of just `depends_on: db`?**
Without the condition, Docker starts the API as soon as the Postgres container starts — not when Postgres is actually ready to accept connections. Postgres takes 2-3 seconds to initialize after the container starts. Without the health check condition, the API tries to connect immediately and crashes with a connection error.

`pg_isready` is a Postgres utility that returns exit code 0 when the server is accepting connections. Docker runs it every 5 seconds until it succeeds 5 times in a row before marking the service healthy.

### Named volume

```yaml
volumes:
  postgres_data:
```

```yaml
db:
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

Without this, database data lives inside the container. When you run `docker-compose down`, the container is destroyed and all data is lost. A named volume persists on the host outside the container lifecycle. `docker-compose down` keeps the volume; only `docker-compose down -v` (or `make clean`) removes it.

### `env_file: .env`

```yaml
api:
  env_file:
    - .env
```

Loads all variables from `.env` into the container's environment. This means `API_KEY`, `DATABASE_URL`, and Postgres credentials are set in one place and shared between both services. No hardcoded credentials in `docker-compose.yml`.

---

## `database.py` — SQLite → PostgreSQL

### What changed and why

| SQLite (Project 4) | PostgreSQL (Project 5) | Reason |
|---|---|---|
| `sqlite3` stdlib | `psycopg2` library | PostgreSQL requires a driver |
| `?` placeholders | `%s` placeholders | psycopg2 uses `%s` style |
| `sqlite3.Row` | `RealDictCursor` | Column-name access |
| JSON string for arrays | `JSONB` native type | PostgreSQL has native JSON |
| `AUTOINCREMENT` | `SERIAL` | PostgreSQL sequence syntax |
| File path | `DATABASE_URL` env var | Network connection, not file |

### `RealDictCursor`

```python
conn = psycopg2.connect(
    get_database_url(),
    cursor_factory=RealDictCursor,
)
```

`RealDictCursor` makes every row accessible by column name: `row["salary"]`. This is the psycopg2 equivalent of sqlite3's `row_factory = sqlite3.Row`. Setting it at connection level means all cursors from this connection use it automatically.

### `JSONB` vs JSON string

In Project 4, skills were stored as `TEXT` containing a JSON string: `'["python", "fastapi"]'`. In Project 5, they're stored as `JSONB` — PostgreSQL's native binary JSON type.

Benefits of JSONB:
- psycopg2 automatically deserializes it to a Python list on read — no `json.loads()` needed
- It's indexable — you can query `WHERE matched_skills @> '["python"]'`
- It validates JSON on write — malformed JSON is rejected at the DB level

### Cursor as context manager

```python
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(...)
        row = cur.fetchone()
    conn.commit()
```

psycopg2 connections and cursors both support the context manager protocol. The cursor is closed automatically on `__exit__`. Note that `conn.commit()` must be called explicitly — psycopg2 defaults to manual commit mode (unlike sqlite3 which auto-commits inside `with` blocks).

---

## `main.py` — PostgreSQL differences

### `RETURNING *` on INSERT

```sql
INSERT INTO scores (...) VALUES (%s, %s, ...) RETURNING *
```

`RETURNING *` tells PostgreSQL to return the newly inserted row immediately. In Project 4 (SQLite), a second `SELECT` was needed to retrieve the row after insert. PostgreSQL's `RETURNING` eliminates that round trip — one query instead of two.

### `%s` placeholders

```python
cur.execute("SELECT * FROM scores WHERE id = %s", (score_id,))
```

psycopg2 uses `%s` for all parameter types (integers, strings, floats). SQLite uses `?`. This is a driver-level difference — both prevent SQL injection by parameterizing the query.

Note the tuple with a trailing comma: `(score_id,)`. A single-element tuple in Python requires the comma — `(score_id)` is just parentheses around an integer, not a tuple.

---

## `Makefile`

### What it does
Provides short memorable commands for common Docker operations.

```makefile
up:     docker-compose up --build -d
down:   docker-compose down
logs:   docker-compose logs -f api
shell:  docker-compose exec api bash
clean:  docker-compose down -v
```

**Why a Makefile?**
`docker-compose up --build -d` is 26 characters with 3 flags to remember. `make up` is 7. Makefiles are available on every Unix system without installation. They're the standard tool for project shortcuts in backend engineering.

**`make clean` vs `make down`**
`make down` stops containers but keeps the database volume — data survives. `make clean` runs `docker-compose down -v` which also removes volumes — data is wiped. Always use `down` in development; only use `clean` when you want a completely fresh state.

---

## `tests/test_api.py` — SQLite mock for psycopg2

### The challenge
Tests shouldn't need Docker running. But the app uses psycopg2 which connects to PostgreSQL. The solution: wrap SQLite in classes that mimic the psycopg2 interface.

### `SQLiteCursor` — the translation layer

```python
class SQLiteCursor:
    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")          # placeholder style
        sql = sql.replace("JSONB", "TEXT")     # type compatibility
        sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        sql = sql.replace("TIMESTAMPTZ", "TEXT")
        sql = sql.replace("NOW()", "datetime('now')")
        # Handle RETURNING * — not supported in SQLite
        returning = "RETURNING *" in sql
        sql = sql.replace("RETURNING *", "")
        ...
        if returning:
            self._cur.execute("SELECT * FROM scores WHERE id = ?", (self._cur.lastrowid,))
```

Key translations:
- `%s` → `?` (placeholder style)
- `SERIAL` → `INTEGER PRIMARY KEY AUTOINCREMENT` (sequence syntax)
- `JSONB` → `TEXT` (type compatibility)
- `RETURNING *` → simulated with a second SELECT using `lastrowid`
- JSONB fields auto-deserialized from JSON strings on `fetchone()`/`fetchall()`

### `SQLiteConnection` — context manager compliance

```python
class SQLiteConnection:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def commit(self): self._conn.commit()
    def cursor(self): return SQLiteCursor(self._conn)
```

psycopg2 connections are used as context managers in the app (`with get_connection() as conn`). The wrapper implements `__enter__` and `__exit__` so the `with` statement works. `commit()` is forwarded to the underlying sqlite3 connection.

### Patching before import

```python
import database
database.get_connection = mock_get_connection  # patch first
from main import app                            # then import
```

`main.py` imports `database` at module level. If `main` was imported first, it would capture the original `get_connection`. Patching the module attribute before importing `main` ensures the app uses the mock throughout.
