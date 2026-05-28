# RAG Engineering — Complete Study Guide

Everything you need to learn, from basics to advanced, for every technology used across all 5 projects. Each section goes from foundational concepts to production-level patterns.

---

## Table of Contents

1. [Python](#1-python)
2. [Regex](#2-regex)
3. [SQL & SQLite](#3-sql--sqlite)
4. [PostgreSQL](#4-postgresql)
5. [FastAPI](#5-fastapi)
6. [Pydantic](#6-pydantic)
7. [Git](#7-git)
8. [Docker](#8-docker)
9. [REST APIs](#9-rest-apis)
10. [Authentication](#10-authentication)
11. [Testing](#11-testing)
12. [Environment & Configuration](#12-environment--configuration)
13. [Command Line (CLI)](#13-command-line-cli)
14. [File Formats (PDF, DOCX, CSV)](#14-file-formats-pdf-docx-csv)

---

## 1. Python

### Level 1 — Foundations

**Variables and types**
```python
name = "Rikesh"          # str
age = 25                 # int
score = 87.5             # float
is_active = True         # bool
skills = ["Python", "SQL"]  # list
config = {"debug": True}    # dict
```

**Functions**
```python
# Basic
def greet(name):
    return f"Hello, {name}"

# With type hints (always use these)
def add(a: int, b: int) -> int:
    return a + b

# Default arguments
def connect(host: str, port: int = 5432) -> str:
    return f"{host}:{port}"

# *args — variable positional arguments
def total(*numbers: int) -> int:
    return sum(numbers)

# **kwargs — variable keyword arguments
def create_user(**fields):
    return fields  # {"name": "...", "email": "..."}
```

**Conditionals and loops**
```python
# Conditionals
if score >= 80:
    grade = "A"
elif score >= 60:
    grade = "B"
else:
    grade = "C"

# For loop
for skill in skills:
    print(skill)

# While loop
count = 0
while count < 5:
    count += 1

# List comprehension — Pythonic way to build lists
squares = [x**2 for x in range(10)]
evens = [x for x in range(20) if x % 2 == 0]
```

**String methods**
```python
text = "  Hello, World!  "
text.strip()         # "Hello, World!"
text.lower()         # "  hello, world!  "
text.upper()         # "  HELLO, WORLD!  "
text.split(", ")     # ["  Hello", "World!  "]
text.replace("Hello", "Hi")
", ".join(["a", "b", "c"])  # "a, b, c"
f"Name: {name}, Age: {age}" # f-string formatting
```

---

### Level 2 — Intermediate

**Dataclasses**
```python
from dataclasses import dataclass, field

@dataclass
class Resume:
    name: str
    email: str = ""
    skills: list[str] = field(default_factory=list)  # not skills: list = []

    def to_dict(self) -> dict:
        return {"name": self.name, "email": self.email}

r = Resume(name="Jane")
r.skills.append("Python")
```

Why `field(default_factory=list)` instead of `= []`:
In Python, mutable default values (`[]`, `{}`) are shared across all instances. `default_factory` creates a fresh object for each instance.

**OOP — Classes**
```python
class ResumeParser:
    # Class variable — shared across all instances
    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-z]+")

    def __init__(self, strict: bool = False):
        # Instance variable — unique to each instance
        self.strict = strict

    def parse(self, text: str) -> Resume:
        """Public method."""
        lines = text.splitlines()
        return Resume(
            name=self._extract_name(lines),
            email=self._extract_email(text),
        )

    def _extract_email(self, text: str) -> str:
        """Private method — convention is leading underscore."""
        match = self.EMAIL_PATTERN.search(text)
        return match.group(0) if match else ""


# Inheritance
class StrictParser(ResumeParser):
    def __init__(self):
        super().__init__(strict=True)  # call parent __init__
```

**Properties**
```python
@dataclass
class ColumnStats:
    count: int
    null_count: int

    @property
    def null_pct(self) -> float:
        """Computed on access, not stored."""
        if self.count == 0:
            return 0.0
        return round((self.null_count / self.count) * 100, 2)

stats = ColumnStats(count=100, null_count=5)
print(stats.null_pct)  # 5.0 — computed automatically
```

**Error handling**
```python
# Specific exceptions (always prefer over bare except)
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"Invalid JSON: {e}")
except FileNotFoundError:
    print("File not found")
except (ValueError, TypeError) as e:
    print(f"Value error: {e}")
finally:
    # Always runs — use for cleanup
    file.close()

# Raising your own exceptions
def load_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text()
```

**File handling**
```python
from pathlib import Path

# Always use 'with' — auto-closes even on error
with open("file.txt", "r", encoding="utf-8") as f:
    content = f.read()          # full file as string
    lines = f.readlines()       # list of lines
    for line in f:              # memory-efficient iteration

# Writing
with open("output.txt", "w") as f:
    f.write("content")

# pathlib — modern way (preferred over os.path)
path = Path("data/resumes/resume.pdf")
path.exists()           # True/False
path.suffix             # ".pdf"
path.stem               # "resume"
path.parent             # Path("data/resumes")
path.read_text()        # shorthand for open + read
path.write_text("...")  # shorthand for open + write
```

**JSON**
```python
import json

# String → Python
data = json.loads('{"name": "Jane", "skills": ["Python"]}')

# Python → String
json_str = json.dumps(data, indent=2)

# File → Python
with open("config.json") as f:
    config = json.load(f)

# Python → File
with open("output.json", "w") as f:
    json.dump(data, f, indent=2)
```

**Collections**
```python
from collections import Counter, defaultdict

# Counter — count occurrences
words = ["python", "python", "sql", "python", "sql"]
count = Counter(words)
count.most_common(2)    # [("python", 3), ("sql", 2)]

# defaultdict — dict with default value for missing keys
groups = defaultdict(list)
for emp in employees:
    groups[emp["dept"]].append(emp["name"])
```

---

### Level 3 — Advanced

**Async / Await**
```python
import asyncio
import httpx

# async function — doesn't block while waiting
async def fetch_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            json={"input": text}
        )
        return response.json()["data"][0]["embedding"]

# Run multiple coroutines concurrently
async def embed_many(texts: list[str]) -> list[list[float]]:
    tasks = [fetch_embedding(t) for t in texts]
    return await asyncio.gather(*tasks)  # all run at once

# Entry point
asyncio.run(embed_many(["text1", "text2"]))
```

Without async: requests run sequentially — 10 API calls × 500ms = 5 seconds.
With async: all 10 run concurrently — ~500ms total.

**Type hints — advanced**
```python
from typing import Optional, Union

def find_score(id: int) -> Optional[float]:    # float or None
    ...

def parse(text: str | bytes) -> str:           # Python 3.10+
    ...

def process(items: list[dict[str, int]]) -> None:
    ...
```

**Context managers**
```python
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = connect()
    try:
        yield conn        # code inside 'with' runs here
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage
with get_db_connection() as conn:
    conn.execute("INSERT ...")
```

**Generators**
```python
# Memory-efficient iteration — doesn't load all rows at once
def read_csv_chunks(path: Path, chunk_size: int = 1000):
    with open(path) as f:
        chunk = []
        for line in f:
            chunk.append(line)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

for chunk in read_csv_chunks("large.csv"):
    process(chunk)
```

**Decorators**
```python
import functools
import time

def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.time() - start:.2f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
```

**Resources**
- Python official tutorial: https://docs.python.org/3/tutorial/
- Real Python: https://realpython.com
- Python type hints: https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html
- Fluent Python (book) — best intermediate-to-advanced Python book

---

## 2. Regex

Used in: `parser.py`, `file_reader.py`

### Core syntax

```
.       any character except newline
\d      digit [0-9]
\w      word character [a-zA-Z0-9_]
\s      whitespace (space, tab, newline)
\b      word boundary
^       start of string (or line with MULTILINE)
$       end of string (or line with MULTILINE)

*       0 or more
+       1 or more
?       0 or 1 (also makes quantifiers non-greedy)
{n}     exactly n
{n,m}   between n and m

[abc]   character class — a, b, or c
[^abc]  negated class — not a, b, or c
(...)   group
|       or
```

### Python regex functions

```python
import re

text = "Jane Smith, jane@email.com, (415) 555-0192"

# search — find first match anywhere in string
match = re.search(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", text)
if match:
    print(match.group(0))    # "Jane Smith"

# findall — return all matches as list
emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-z]+", text)

# sub — replace matches
clean = re.sub(r"\s+", " ", text)          # collapse whitespace
clean = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # remove headers

# split — split on pattern
parts = re.split(r"[,|•]\s*", "Python, SQL | Docker • AWS")

# compile — pre-compile for reuse (faster in loops)
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-z]+")
match = EMAIL_PATTERN.search(text)
```

### Flags

```python
re.IGNORECASE   # case-insensitive matching
re.MULTILINE    # ^ and $ match start/end of each line
re.DOTALL       # . matches newline too
```

### Groups and capture

```python
# () creates a capture group
pattern = re.compile(r"(\w+)\s(\w+)")  # first last
match = pattern.search("Jane Smith")
match.group(0)   # "Jane Smith" — full match
match.group(1)   # "Jane" — group 1
match.group(2)   # "Smith" — group 2

# Named groups
pattern = re.compile(r"(?P<first>\w+)\s(?P<last>\w+)")
match.group("first")  # "Jane"
```

### Common patterns used in projects

```python
EMAIL    = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE    = r"(\+?1?\s?)?(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})"
YEAR     = r"\b(19|20)\d{2}\b"
DATE     = r"\b(Jan|Feb|Mar|...|December)\s+\d{4}\b"
CAMEL    = r"([a-z])([A-Z][a-z])"   # split CamelCase
```

**Resources**
- regex101.com — test patterns interactively with explanation
- https://docs.python.org/3/library/re.html
- Regular Expressions Cookbook (book)

---

## 3. SQL & SQLite

Used in: Projects 3 and 4

### Level 1 — SELECT basics

```sql
-- All columns
SELECT * FROM employees;

-- Specific columns with alias
SELECT name, salary, salary * 1.1 AS salary_with_raise
FROM employees;

-- Filter
WHERE salary > 80000
WHERE department = 'Engineering'
WHERE hire_date BETWEEN '2020-01-01' AND '2023-12-31'
WHERE name LIKE 'J%'          -- starts with J
WHERE department IN ('Eng', 'Data')

-- Sort and limit
ORDER BY salary DESC
LIMIT 10 OFFSET 20            -- page 3 of 10 results
```

### Level 2 — JOINs

```sql
-- INNER JOIN — only matching rows
SELECT e.name, d.name AS department
FROM employees e
INNER JOIN departments d ON e.department_id = d.id;

-- LEFT JOIN — all left rows, NULLs where no match
SELECT e.name, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id;

-- Three-table join
SELECT e.name, d.name AS dept, l.city
FROM employees e
JOIN departments d ON e.department_id = d.id
JOIN locations l ON d.location_id = l.id;
```

Mental model:
- `INNER JOIN` = intersection — only rows that exist in both tables
- `LEFT JOIN` = keep everything on the left, NULL where no match on right

### Level 3 — GROUP BY

```sql
-- Basic aggregates
SELECT
    department_id,
    COUNT(*)                AS headcount,
    AVG(salary)             AS avg_salary,
    MIN(salary)             AS min_salary,
    MAX(salary)             AS max_salary,
    SUM(salary)             AS total_payroll
FROM employees
GROUP BY department_id;

-- HAVING — filter after grouping (WHERE filters before)
SELECT department_id, COUNT(*) AS headcount
FROM employees
GROUP BY department_id
HAVING COUNT(*) > 10;

-- Conditional aggregation
SELECT
    COUNT(CASE WHEN is_remote = 1 THEN 1 END) AS remote_count,
    COUNT(CASE WHEN is_remote = 0 THEN 1 END) AS office_count
FROM employees;
```

Rule: every column in SELECT must be in GROUP BY or in an aggregate function.

### Level 4 — Window Functions

Window functions compute aggregates without collapsing rows.

```sql
-- RANK within a group
SELECT
    name,
    department_id,
    salary,
    RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS rank
FROM employees;

-- Running total
SELECT
    hire_date,
    salary,
    SUM(salary) OVER (ORDER BY hire_date) AS running_total
FROM employees;

-- Compare to group average
SELECT
    name,
    salary,
    AVG(salary) OVER (PARTITION BY department_id) AS dept_avg,
    salary - AVG(salary) OVER (PARTITION BY department_id) AS diff
FROM employees;
```

Key window functions:
```
RANK()          -- 1, 2, 2, 4 (skips after tie)
DENSE_RANK()    -- 1, 2, 2, 3 (no skip)
ROW_NUMBER()    -- 1, 2, 3, 4 (unique always)
LAG(col, n)     -- value from n rows before
LEAD(col, n)    -- value from n rows after
SUM() OVER      -- running total
AVG() OVER      -- running/group average
```

### Level 5 — Subqueries

```sql
-- Subquery in WHERE
SELECT name, salary
FROM employees
WHERE salary > (SELECT AVG(salary) FROM employees);

-- Subquery in FROM (derived table)
SELECT dept, rank
FROM (
    SELECT name, dept, RANK() OVER (...) AS rank
    FROM employees
)
WHERE rank <= 3;

-- Correlated subquery — references outer query
SELECT name
FROM employees e
WHERE salary = (
    SELECT MAX(salary)
    FROM employees
    WHERE department_id = e.department_id  -- ← outer reference
);
```

### Level 6 — Indexes

```sql
-- Create
CREATE INDEX idx_employees_dept ON employees(department_id);

-- Composite (order matters — most selective column first)
CREATE INDEX idx_emp_dept_salary ON employees(department_id, salary);

-- Unique
CREATE UNIQUE INDEX idx_employees_email ON employees(email);

-- Analyze query plan
EXPLAIN QUERY PLAN
SELECT * FROM employees WHERE department_id = 3;
```

Index on a column when:
- It appears in `WHERE` clauses frequently
- It appears in `JOIN ON` conditions
- It appears in `ORDER BY` clauses
- It has high cardinality (many unique values)

### SQLite-specific

```python
import sqlite3

conn = sqlite3.connect("mydb.db")
conn.row_factory = sqlite3.Row      # column-name access
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")

cur = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,))
row = cur.fetchone()
rows = cur.fetchall()
print(row["salary"])   # column by name

conn.commit()
conn.close()

# As context manager
with sqlite3.connect("mydb.db") as conn:
    conn.execute("INSERT INTO ...")
    # auto-commits on exit
```

**Resources**
- SQLZoo: https://sqlzoo.net — interactive exercises
- Mode SQL Tutorial: https://mode.com/sql-tutorial — window functions
- Use The Index, Luke: https://use-the-index-luke.com — indexes
- LeetCode SQL 50: https://leetcode.com/studyplan/top-sql-50/

---

## 4. PostgreSQL

Used in: Project 5

### Differences from SQLite

| SQLite | PostgreSQL |
|---|---|
| File-based | Server-based |
| No native types for arrays/JSON | JSONB, arrays, UUID natively |
| `?` placeholders | `%s` placeholders |
| `AUTOINCREMENT` | `SERIAL` or `GENERATED ALWAYS AS IDENTITY` |
| `datetime('now')` | `NOW()` |
| Limited concurrent writes | Full MVCC concurrency |

### psycopg2

```python
import psycopg2
from psycopg2.extras import RealDictCursor

# Connect
conn = psycopg2.connect(
    "postgresql://user:password@host:5432/dbname",
    cursor_factory=RealDictCursor,   # row["column"] access
)

# Execute queries
with conn.cursor() as cur:
    cur.execute("SELECT * FROM scores WHERE score >= %s", (70,))
    rows = cur.fetchall()       # list of RealDictRow
    one = cur.fetchone()        # single RealDictRow

# Always commit manually (psycopg2 doesn't auto-commit)
conn.commit()

# RETURNING — get inserted row immediately
with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO scores (name, score) VALUES (%s, %s) RETURNING *",
        ("Jane", 85.5)
    )
    new_row = cur.fetchone()   # inserted row
conn.commit()
```

### JSONB

```sql
-- JSONB column — native JSON, binary stored, indexable
CREATE TABLE scores (
    matched_skills JSONB DEFAULT '[]'
);

-- Query inside JSONB
SELECT * FROM scores WHERE matched_skills @> '["python"]';

-- Index on JSONB
CREATE INDEX idx_skills ON scores USING GIN(matched_skills);
```

psycopg2 automatically converts JSONB → Python list/dict on read. No `json.loads()` needed.

### PostgreSQL-specific SQL

```sql
-- SERIAL — auto-incrementing integer
id SERIAL PRIMARY KEY

-- TIMESTAMPTZ — timestamp with timezone
created_at TIMESTAMPTZ DEFAULT NOW()

-- UPSERT — insert or update on conflict
INSERT INTO scores (candidate_id, score)
VALUES (1, 85)
ON CONFLICT (candidate_id)
DO UPDATE SET score = EXCLUDED.score;

-- CTEs (Common Table Expressions) — named subqueries
WITH dept_avg AS (
    SELECT department_id, AVG(salary) AS avg_sal
    FROM employees
    GROUP BY department_id
)
SELECT e.name, e.salary, da.avg_sal
FROM employees e
JOIN dept_avg da ON e.department_id = da.department_id;
```

**Resources**
- PostgreSQL official docs: https://www.postgresql.org/docs/
- psycopg2 docs: https://www.psycopg.org/docs/
- PostgreSQL Exercises: https://pgexercises.com

---

## 5. FastAPI

Used in: Projects 4 and 5

### Level 1 — Basics

```python
from fastapi import FastAPI

app = FastAPI(title="My API", version="1.0.0")

# GET route
@app.get("/")
def root():
    return {"status": "ok"}

# Path parameter
@app.get("/items/{item_id}")
def get_item(item_id: int):   # FastAPI validates type automatically
    return {"id": item_id}

# Query parameters
@app.get("/items")
def list_items(limit: int = 10, offset: int = 0):
    return {"limit": limit, "offset": offset}
```

Run with: `uvicorn main:app --reload`
Docs at: `http://localhost:8000/docs`

### Level 2 — Request bodies

```python
from pydantic import BaseModel
from fastapi import FastAPI

class CreateItemRequest(BaseModel):
    name: str
    price: float
    in_stock: bool = True

@app.post("/items", status_code=201)
def create_item(body: CreateItemRequest):
    # body.name, body.price, body.in_stock are validated automatically
    return {"id": 1, **body.model_dump()}
```

### Level 3 — Dependency injection

```python
from fastapi import Depends, HTTPException

def get_current_user(token: str = Header(...)):
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401)
    return user

@app.get("/profile")
def get_profile(user = Depends(get_current_user)):
    return user  # injected automatically
```

### Level 4 — Security

```python
from fastapi import Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_key(key: str = Security(api_key_header)):
    if key != "secret":
        raise HTTPException(status_code=401)
    return key

@app.post("/protected")
def protected_route(_: str = Security(verify_key)):
    return {"message": "authorized"}
```

### Level 5 — Lifespan and middleware

```python
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — runs once when server starts
    init_db()
    print("Server started")
    yield
    # Shutdown — runs once when server stops
    print("Server stopped")

app = FastAPI(lifespan=lifespan)

# CORS middleware — allow browser requests from different origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### HTTP status codes

```python
from fastapi import status

status.HTTP_200_OK           # 200
status.HTTP_201_CREATED      # 201
status.HTTP_400_BAD_REQUEST  # 400
status.HTTP_401_UNAUTHORIZED # 401
status.HTTP_403_FORBIDDEN    # 403
status.HTTP_404_NOT_FOUND    # 404
status.HTTP_422_UNPROCESSABLE_ENTITY  # 422 (Pydantic validation fail)
status.HTTP_500_INTERNAL_SERVER_ERROR # 500
```

### Error handling

```python
from fastapi import HTTPException

@app.get("/scores/{id}")
def get_score(id: int):
    score = db.find(id)
    if not score:
        raise HTTPException(
            status_code=404,
            detail=f"Score {id} not found"
        )
    return score
```

**Resources**
- FastAPI official docs: https://fastapi.tiangolo.com — best framework docs in existence
- FastAPI full course: https://testdriven.io/blog/fastapi-crud/

---

## 6. Pydantic

Used in: Projects 4 and 5

### Level 1 — Basic models

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str
    age: int

# Validation on creation
user = User(name="Jane", email="jane@email.com", age=25)
user.name     # "Jane"
user.model_dump()  # {"name": "Jane", "email": "...", "age": 25}
```

### Level 2 — Field validation

```python
from pydantic import BaseModel, Field

class ScoreRequest(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=100)
    resume_text: str = Field(min_length=10)
    score: float = Field(ge=0, le=100)         # 0 ≤ score ≤ 100
    job_title: str = Field(default="")         # optional with default
```

Field validators:
```
min_length, max_length   — string length
ge, le, gt, lt           — numeric comparisons (≥, ≤, >, <)
pattern                  — regex pattern
default                  — default value
description              — shown in /docs
```

### Level 3 — Nested models and config

```python
class Address(BaseModel):
    city: str
    country: str = "India"

class Employee(BaseModel):
    name: str
    address: Address   # nested model

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Rikesh",
                "address": {"city": "Patna"}
            }
        }
    }

emp = Employee(name="Rikesh", address={"city": "Patna"})
emp.address.city   # "Patna"
```

**Resources**
- Pydantic v2 docs: https://docs.pydantic.dev/latest/

---

## 7. Git

Used in: All projects

### Level 1 — Daily workflow

```bash
# Setup (one time)
git config --global user.name "Your Name"
git config --global user.email "you@email.com"

# Start a project
git init
git clone https://github.com/user/repo

# Daily loop
git status              # what changed?
git add file.py         # stage a file
git add .               # stage everything
git commit -m "message" # save snapshot
git push origin main    # send to GitHub
git pull origin main    # get latest from GitHub
```

### Level 2 — Branching

```bash
# Create and switch to new branch
git checkout -b feature/scoring-api

# Switch between branches
git checkout main
git checkout feature/scoring-api

# Merge branch into main
git checkout main
git merge feature/scoring-api

# Delete merged branch
git branch -d feature/scoring-api

# See all branches
git branch -a
```

### Level 3 — Undoing things

```bash
# Discard unstaged changes to a file
git restore file.py

# Unstage a file (keep changes)
git restore --staged file.py

# Undo last commit (keep changes unstaged)
git reset HEAD~1

# Undo last commit (keep changes staged)
git reset --soft HEAD~1

# Create a new commit that undoes a previous one (safe for shared branches)
git revert <commit-hash>

# See commit history
git log --oneline
git log --oneline --graph --all  # visual branch graph
```

### Level 4 — Advanced

```bash
# Stash work in progress
git stash              # save current changes
git stash pop          # restore them

# Cherry-pick a commit from another branch
git cherry-pick <commit-hash>

# Create a branch from a specific commit (for old version)
git checkout -b old-version e4f5g6h

# Amend last commit message
git commit --amend -m "corrected message"

# See what changed in a commit
git show <commit-hash>

# Compare branches
git diff main..feature/scoring-api
```

### `.gitignore` — always include

```
__pycache__/
*.pyc
.env                # never commit secrets
*.db                # local databases
.venv/
venv/
.DS_Store
.pytest_cache/
*.egg-info/
```

### Conventional commits

Standard commit message format used in professional projects:
```
feat: add PDF support to resume parser
fix: normalize unicode characters in PDF extraction
docs: update README with setup instructions
refactor: extract file_reader from main.py
test: add education parser tests
chore: update requirements.txt
```

**Resources**
- Pro Git book (free): https://git-scm.com/book/en/v2
- Learn Git Branching (visual): https://learngitbranching.js.org
- Conventional commits: https://www.conventionalcommits.org

---

## 8. Docker

Used in: Project 5

### Level 1 — Core concepts

| Term | Meaning |
|---|---|
| Image | Blueprint — a read-only snapshot of your app + environment |
| Container | A running instance of an image |
| Dockerfile | Instructions for building an image |
| docker-compose | Tool for running multiple containers together |
| Volume | Persistent storage that survives container restarts |
| Registry | Storage for images (Docker Hub, GitHub Container Registry) |

### Level 2 — Dockerfile

```dockerfile
# Base image — use slim variants for smaller size
FROM python:3.11-slim

# Working directory inside container
WORKDIR /app

# Copy requirements FIRST for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code AFTER dependencies
COPY . .

# Port the app listens on (documentation only)
EXPOSE 8000

# Command to run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Layer caching explained:**
Docker builds in layers. Each instruction is a layer. Layers are cached — if nothing changed, Docker reuses the cached layer. Copying `requirements.txt` before code means code changes don't trigger a full pip reinstall.

### Level 3 — Docker Compose

```yaml
version: "3.9"

services:
  api:
    build: .                      # build from Dockerfile
    ports:
      - "8000:8000"               # host:container
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 5

volumes:
  postgres_data:      # named volume — persists after container stops
```

### Level 4 — Essential commands

```bash
# Images
docker build -t my-api .            # build image
docker images                       # list images
docker rmi my-api                   # remove image

# Containers
docker run -p 8000:8000 my-api      # run container
docker run -d -p 8000:8000 my-api   # run in background
docker ps                           # list running
docker ps -a                        # include stopped
docker stop <id>                    # stop
docker rm <id>                      # remove

# Debugging
docker logs <id>                    # view logs
docker logs -f <id>                 # stream logs
docker exec -it <id> bash           # shell into container

# Compose
docker-compose up --build           # build + start
docker-compose up -d                # start in background
docker-compose down                 # stop + remove containers
docker-compose down -v              # also remove volumes
docker-compose logs -f api          # stream service logs
docker-compose exec api bash        # shell into service
```

### Level 5 — Multi-stage build

```dockerfile
# Stage 1: build
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: final — smaller image, no build tools
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY . .

# Security: run as non-root user
RUN adduser --system appuser
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Resources**
- Docker official docs: https://docs.docker.com/get-started/
- Docker + FastAPI: https://fastapi.tiangolo.com/deployment/docker/
- Docker Compose docs: https://docs.docker.com/compose/

---

## 9. REST APIs

Used in: Projects 4 and 5

### HTTP methods

| Method | Usage | Idempotent |
|---|---|---|
| GET | Read data | ✅ |
| POST | Create resource | ❌ |
| PUT | Replace resource | ✅ |
| PATCH | Partial update | ❌ |
| DELETE | Delete resource | ✅ |

Idempotent = calling it multiple times has the same effect as calling it once.

### URL design

```
GET    /scores          → list all scores
GET    /scores/42       → get score 42
POST   /scores          → create a new score
PUT    /scores/42       → replace score 42
PATCH  /scores/42       → partially update score 42
DELETE /scores/42       → delete score 42
```

Rules:
- Nouns not verbs in URLs (`/scores` not `/getScores`)
- Plural nouns for collections (`/scores` not `/score`)
- Nested resources: `/users/42/scores`
- Query params for filtering: `/scores?min_score=70&limit=10`

### Status codes

```
2xx — Success
  200 OK           — standard success
  201 Created      — resource created (POST)
  204 No Content   — success, no body (DELETE sometimes)

4xx — Client error (your fault)
  400 Bad Request         — malformed request
  401 Unauthorized        — missing/invalid credentials
  403 Forbidden           — authenticated but not permitted
  404 Not Found           — resource doesn't exist
  422 Unprocessable       — validation failed (Pydantic)
  429 Too Many Requests   — rate limited

5xx — Server error (our fault)
  500 Internal Server Error — unhandled exception
  503 Service Unavailable   — server overloaded/down
```

### Request/Response anatomy

```
POST /scores HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-API-Key: secret-key-here

{
  "candidate_name": "Jane",
  "resume_text": "...",
  "job_description": "..."
}
```

```
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": 1,
  "score": 85.5,
  "recommendation": "Strong match"
}
```

**Resources**
- RESTful API Design: https://restfulapi.net
- HTTP Status Codes: https://httpstatuses.com
- HTTP Cats: https://http.cat (genuinely useful)

---

## 10. Authentication

Used in: Projects 4 and 5

### API Key Auth

Simplest form — client includes a secret key in a header:

```
Request header: X-API-Key: your-secret-key
```

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str = Security(api_key_header)):
    if not key or key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key
```

Best for: server-to-server communication, internal tools.

### JWT (JSON Web Tokens)

Tokens carry identity claims — user ID, roles, expiry:

```python
import jwt
from datetime import datetime, timedelta

SECRET = "your-secret"

def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

Best for: user-facing apps where tokens need to expire and carry user info.

### OAuth2

Delegated authorization — "Login with Google":
- You never see the user's Google password
- Google gives you a token after user consents
- You use that token to access user data

In production: use Auth0, Clerk, or Supabase instead of rolling your own.

### 401 vs 403

- **401 Unauthorized** — "I don't know who you are." Missing or invalid credentials.
- **403 Forbidden** — "I know who you are, but you can't do this." Valid credentials, insufficient permissions.

---

## 11. Testing

Used in: All projects

### pytest basics

```bash
pip install pytest httpx

pytest tests/              # run all tests
pytest tests/ -v           # verbose — show each test name
pytest tests/ -k "Auth"    # run only tests matching "Auth"
pytest tests/ -x           # stop on first failure
```

```python
import pytest

def test_addition():
    assert 1 + 1 == 2

def test_with_message():
    result = parse("Jane Smith")
    assert result.name == "Jane Smith", f"Got: {result.name}"

# Test that an exception is raised
def test_raises():
    with pytest.raises(FileNotFoundError):
        load_file(Path("nonexistent.txt"))
```

### Fixtures

```python
@pytest.fixture
def sample_resume() -> str:
    return "Jane Smith\njane@email.com\nSkills: Python"

@pytest.fixture(scope="module")  # created once per module
def test_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    init_db(db_path)
    seed(db_path, num_employees=50)
    return db_path

def test_parse_name(sample_resume):  # fixture injected automatically
    result = ResumeParser().parse(sample_resume)
    assert result.name == "Jane Smith"
```

### FastAPI TestClient

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_create_score():
    r = client.post("/scores",
        json={"candidate_name": "Jane", "resume_text": "..." , "job_description": "..."},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 201
    assert "score" in r.json()
```

### Test organization

```python
# Group related tests in classes
class TestAuth:
    def test_missing_key_401(self): ...
    def test_wrong_key_401(self): ...
    def test_valid_key_passes(self): ...

class TestCreateScore:
    def test_valid_returns_201(self): ...
    def test_short_resume_422(self): ...
    def test_empty_name_422(self): ...
```

### What to test

- **Happy path** — does it work when everything is correct?
- **Validation** — does it reject bad input?
- **Not found** — does it return 404 for missing resources?
- **Auth** — does it reject missing/wrong credentials?
- **Edge cases** — empty strings, very large inputs, special characters?

**Resources**
- pytest docs: https://docs.pytest.org
- FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/

---

## 12. Environment & Configuration

Used in: Projects 4 and 5

### Environment variables

Never hardcode secrets in code. Store them in environment variables:

```python
import os

# Read env var — returns None if not set
api_key = os.getenv("API_KEY")

# With default
debug = os.getenv("DEBUG", "false").lower() == "true"

# Raise if missing (fail fast)
db_url = os.environ["DATABASE_URL"]  # KeyError if not set
```

### python-dotenv

Loads a `.env` file into `os.environ`:

```python
from dotenv import load_dotenv

load_dotenv()  # reads .env from current directory
api_key = os.getenv("API_KEY")
```

```bash
# .env file (never commit this)
API_KEY=your-secret-key
DATABASE_URL=postgresql://postgres:pass@localhost:5432/mydb

# .env.example (always commit this — template for others)
API_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

### .gitignore for secrets

```
.env          # ← never commit
.env.local
*.db
```

`.env.example` shows what variables exist without revealing values. Anyone cloning the repo copies it and fills in their own values.

---

## 13. Command Line (CLI)

Used in: Projects 1, 2, 3

### argparse

```python
import argparse

parser = argparse.ArgumentParser(
    description="Parse a resume into structured JSON",
    epilog="Example: python main.py resume.pdf --section skills"
)

# Positional argument (required)
parser.add_argument("file", type=Path, help="Path to resume file")

# Optional flag with value
parser.add_argument("--output", "-o", type=Path, help="Save output to file")

# Choice argument
parser.add_argument("--format", choices=["json", "pretty"], default="pretty")

# Boolean flag
parser.add_argument("--verbose", action="store_true")

args = parser.parse_args()
print(args.file)      # Path object
print(args.output)    # Path or None
print(args.verbose)   # True or False
```

```bash
python main.py resume.pdf --output result.json --format pretty
python main.py resume.pdf -o result.json       # short flag
```

### stdout vs stderr

```python
import sys

# Normal output → stdout (pipeable)
print(json.dumps(data))

# Errors and messages → stderr (don't pollute stdout)
print("Error: file not found", file=sys.stderr)

# Exit codes
sys.exit(0)   # success
sys.exit(1)   # failure
```

This matters for piping: `python main.py resume.txt --section skills | sort`
If errors went to stdout, `sort` would try to sort the error message.

---

## 14. File Formats (PDF, DOCX, CSV)

Used in: Projects 1.5 and 2

### PDF — pdfplumber

```python
import pdfplumber

with pdfplumber.open("resume.pdf") as pdf:
    for page in pdf.pages:
        # Method 1: raw text (may have spacing issues)
        text = page.extract_text(x_tolerance=2, y_tolerance=3)

        # Method 2: word-based (more reliable)
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=3,
            use_text_flow=True,  # follow reading order
        )

        # Method 3: tables
        tables = page.extract_tables()
```

Why PDFs are hard: PDFs store characters at absolute X/Y coordinates on a page. There's no concept of "space between words" in the format — the parser has to infer spaces from gaps between character positions.

### DOCX — python-docx

```python
from docx import Document

doc = Document("resume.docx")

# Paragraphs
for para in doc.paragraphs:
    print(para.text)       # plain text
    print(para.style.name) # "Heading 1", "Normal", etc.

# Tables
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            print(cell.text)
```

### CSV — stdlib

```python
import csv

# Read
with open("data.csv", newline="") as f:
    reader = csv.DictReader(f)  # rows as dicts
    for row in reader:
        print(row["name"], row["salary"])

# Auto-detect delimiter
with open("data.csv") as f:
    sample = f.read(4096)
    f.seek(0)
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    reader = csv.DictReader(f, dialect=dialect)

# Write
with open("output.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["name", "score"])
    writer.writeheader()
    writer.writerows([{"name": "Jane", "score": 85}])
```

---

## Learning Path

Follow this order for the most efficient progression:

```
Week 1-2:  Python Levels 1-2 (functions, OOP, file handling, JSON)
Week 3:    Regex basics + Python error handling
Week 4:    SQL Levels 1-3 (SELECT, JOINs, GROUP BY)
Week 5:    SQL Levels 4-5 (Window functions, subqueries, indexes)
Week 6:    REST APIs + FastAPI Levels 1-3
Week 7:    FastAPI Levels 4-5 + Pydantic
Week 8:    Git Levels 1-3
Week 9:    Docker Levels 1-3
Week 10:   Docker Compose + PostgreSQL
Week 11:   Testing with pytest
Week 12:   Build all 5 projects end to end
```

## Quick Reference — What each project teaches

| Project | Primary Skills |
|---|---|
| 01 CLI Resume Parser | Python OOP, Regex, File I/O, argparse, dataclasses |
| 01.5 Multi-format Parser | Dispatch pattern, PDF/DOCX parsing, Unicode handling |
| 02 CSV Analyzer | Statistics from scratch, type detection, formatting separation |
| 03 Employee Analytics DB | SQL all levels, SQLite, normalized schema, seeding |
| 04 Resume Scoring API | FastAPI, Pydantic, REST, Auth, SQLite persistence |
| 05 Dockerized API | Docker, Compose, PostgreSQL, psycopg2, multi-stage builds |

---

## 15. Vector Databases & pgvector

Used in: Projects 08, 13+

### What is a vector database?

A vector database stores high-dimensional float arrays (embeddings) and supports efficient nearest-neighbour search — finding vectors most similar to a query vector.

```sql
-- pgvector: store embeddings as a native column type
CREATE TABLE documents (
    id        SERIAL PRIMARY KEY,
    content   TEXT,
    embedding vector(1536)   -- 1536-dimensional OpenAI embedding
);

-- HNSW index for fast approximate search
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);

-- Cosine similarity search
SELECT *, 1 - (embedding <=> '[0.1, -0.2, ...]'::vector) AS score
FROM documents
ORDER BY embedding <=> '[0.1, -0.2, ...]'::vector
LIMIT 5;
```

### Key operators
```
<=>   cosine distance    (0 = identical, 2 = opposite)
<->   euclidean distance
<#>   negative inner product
```

### HNSW vs IVFFlat

| | HNSW | IVFFlat |
|---|---|---|
| Query speed | Faster | Slower |
| Build time | Slower | Faster |
| Memory | More | Less |
| Use case | Production APIs | Large batch indexing |

**Resources**
- pgvector GitHub: https://github.com/pgvector/pgvector
- pgvector docs: https://github.com/pgvector/pgvector#querying

---

## 16. Embeddings & Semantic Search

Used in: Projects 07, 08, 13+

### What are embeddings?

Embeddings are lists of floats that represent the semantic meaning of text. Similar texts produce similar vectors. This enables search by meaning rather than keyword matching.

```python
# OpenAI embedding — 1536 floats
import openai
response = openai.embeddings.create(
    model="text-embedding-3-small",
    input="What is retrieval-augmented generation?"
)
vector = response.data[0].embedding   # list of 1536 floats
```

### Cosine similarity

```python
import math

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x**2 for x in a))
    mag_b = math.sqrt(sum(x**2 for x in b))
    return dot / (mag_a * mag_b)  # 1.0 = identical, 0.0 = unrelated

# For unit-normalized vectors (what all embedding models return):
# cosine_similarity = dot_product
```

### Choosing an embedding model

| Model | Dimensions | Cost | Best for |
|---|---|---|---|
| `text-embedding-3-small` | 1536 | $0.02/1M tokens | General RAG |
| `text-embedding-3-large` | 3072 | $0.13/1M tokens | High-precision retrieval |
| `sentence-transformers` | 384–768 | Free (local) | Privacy-sensitive data |

**Resources**
- OpenAI embeddings: https://platform.openai.com/docs/guides/embeddings
- Sentence Transformers: https://www.sbert.net/

---

## 17. RAG Systems

Used in: Projects 13–20

### The RAG loop

```
INGESTION (one time):
  Document → Chunk → Embed → Store in vector DB

QUERY (every request):
  User question → Embed → Vector search → Top-k chunks
       → Build prompt with chunks as context → LLM → Answer + Citations
```

### Chunking strategies

| Strategy | How | Best for |
|---|---|---|
| Fixed size | Every N characters with overlap | Baseline |
| Sentence | Respect sentence boundaries | Prose, articles |
| Recursive | Try `\n\n` → `\n` → `. ` → ` ` | General purpose |
| Token | Count tokens (tiktoken) | Context window control |

### Retrieval strategies

**Pure vector search** — semantic similarity only. Misses exact keyword matches.

**BM25 keyword search** — exact matches only. Misses semantic variants.

**Hybrid search** — combines both with Reciprocal Rank Fusion (RRF):
```python
# RRF score — k=60 is standard
def rrf_score(rank: int, k: int = 60) -> float:
    return 1 / (k + rank)

# Combine vector rank and BM25 rank
combined_score = rrf_score(vector_rank) + rrf_score(bm25_rank)
```

### Prompt structure for RAG

```
System: "Answer using only the provided context. Do not make up information."

User:
Context:
[1] Source: file.txt
{chunk content}

[2] Source: other.txt
{chunk content}

Question: {user question}

Answer based only on the context above:
```

### RAG evaluation metrics

| Metric | Measures | Good score |
|---|---|---|
| Faithfulness | Are all claims in the answer supported by context? | > 0.8 |
| Answer relevance | Does the answer address the question? | > 0.8 |
| Context recall | Did retrieval find the right chunks? | > 0.7 |
| Context precision | Were retrieved chunks actually useful? | > 0.7 |

**Resources**
- RAGAS: https://docs.ragas.io/
- LangChain RAG tutorial: https://python.langchain.com/docs/tutorials/rag/
- RAG paper (Lewis et al.): https://arxiv.org/abs/2005.11401

---

## 18. Prompt Engineering

Used in: Projects 11, 13+

### Core techniques

**Standard RAG prompt**
Provide context, ask question. Best baseline — use this first.

**Chain-of-thought (CoT)**
```
"Let's think step by step:
1. What does the context tell us?
2. What is directly stated vs implied?
3. What is the final answer?"
```
Forces reasoning before the final answer. Improves accuracy on complex questions.

**Few-shot prompting**
```
Example 1:
Context: The Eiffel Tower was built in 1889.
Question: When was the Eiffel Tower built?
Answer: The Eiffel Tower was built in 1889.

Now answer:
Context: {context}
Question: {question}
Answer:
```
Examples guide format, length, and citation style. 2-3 examples are usually enough.

**HyDE (Hypothetical Document Embeddings)**
Instead of embedding the query, generate a hypothetical answer and embed that:
```python
# Step 1: Generate a fake document that would answer the query
hypothetical = await llm.complete("Write a document excerpt that answers: " + query)

# Step 2: Embed the hypothetical document (more similar to real docs than the query)
query_embedding = await embedder.embed(hypothetical)

# Step 3: Search with the hypothetical embedding
results = await vector_store.search(query_embedding, k=5)
```

**Query rewriting**
Let the LLM improve the query before retrieval:
```python
rewritten = await llm.complete(
    f"Rewrite this query to improve document retrieval. "
    f"Add relevant keywords, expand abbreviations.\n\nQuery: {query}"
)
results = await retriever.retrieve(rewritten)
```

### Jinja2 for prompt templates

```python
from jinja2 import Environment

env = Environment()
template = env.from_string("""
{% if examples %}
{% for ex in examples %}
Q: {{ ex.question }}
A: {{ ex.answer }}
{% endfor %}
{% endif %}
Question: {{ question }}
Context: {{ context }}
""")

prompt = template.render(question="What is RAG?", context="...", examples=[...])
```

**Resources**
- Anthropic prompt engineering guide: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview
- OpenAI prompt engineering: https://platform.openai.com/docs/guides/prompt-engineering

---

## 19. LLM APIs

Used in: Projects 10, 11, 12, 13+

### Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(api_key="your-key")

# Basic completion
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "What is RAG?"}],
)
print(response.content[0].text)
print(response.usage.input_tokens, response.usage.output_tokens)

# Async
import anthropic
client = anthropic.AsyncAnthropic()
response = await client.messages.create(...)

# Streaming
async with client.messages.stream(...) as stream:
    async for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Token counting + cost estimation

```python
# Approximate: 1 token ≈ 4 characters
approx_tokens = len(text) // 4

# Exact (requires tiktoken)
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
exact_tokens = len(enc.encode(text))

# Cost (claude-3-5-haiku-20241022)
INPUT_PRICE  = 0.80   # per 1M tokens
OUTPUT_PRICE = 4.00   # per 1M tokens
cost = (input_tokens / 1_000_000) * INPUT_PRICE + (output_tokens / 1_000_000) * OUTPUT_PRICE
```

### Retry with exponential backoff

```python
import asyncio, random

async def call_with_retry(fn, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except RateLimitError:
            if attempt == max_retries:
                raise
            delay = (2 ** attempt) + random.uniform(0, 1)  # jitter
            await asyncio.sleep(delay)
```

**Resources**
- Anthropic API docs: https://docs.anthropic.com/
- Anthropic Python SDK: https://github.com/anthropic-sdk/anthropic-sdk-python

---

## 20. Domain-Specific RAG Applications (Phase 5)

Used in: Projects 21–27

Each Phase 5 project applies the full RAG stack to a real-world industry domain.
The core pipeline is identical — what changes is the data, the chunking strategy,
the retrieval filters, and the prompt templates.

### Smart City (Project 21)

Key data types: civic service docs, bylaws, infrastructure reports, 311 request logs.

```python
# Example: query the city's building permit regulations
result = await rag.query(
    "What permits do I need to build a rooftop garden?",
    collection="building_regulations",
    k=7,
)
```

Chunking tip: regulatory documents chunk well at section boundaries (keep section headings with their content).

### Education & Research (Project 22)

Key data types: academic papers (PDF), textbooks, syllabi, lecture notes.

```python
# Chunk academic papers by section: Abstract, Introduction, Methods, Results
# Use metadata filters for subject area, year, author
result = await rag.query(
    "What are the main limitations of RAG systems?",
    collection="ai_papers_2024",
    metadata_filter={"topic": "RAG"},
)
```

HyDE works especially well for academic queries — the hypothetical document mimics paper language better than the casual query does.

### Transport (Project 23)

Key data types: timetables (structured), regulations, route maps, incident reports.

```python
# Structured + unstructured hybrid:
# - Structured: timetable lookups via SQL
# - Unstructured: regulation text via RAG
result = await rag.query(
    "What are the rules for carrying bicycles on trains?",
    collection="rail_regulations",
)
```

### Healthcare (Project 27)

**Important: never use RAG for clinical decisions in production without medical review.**

Key data types: clinical guidelines, drug interaction databases, research papers.

```python
# Always include a safety disclaimer in the system prompt
system = """You are a medical information assistant.
IMPORTANT: This information is for educational purposes only.
Always consult a qualified healthcare professional for medical advice."""

result = await rag.query(
    "What are the contraindications for metformin?",
    collection="drug_guidelines",
    system_prompt=system,
)
```

Faithfulness is critical in healthcare RAG — hallucinations can cause harm. Always evaluate with strict faithfulness metrics and add human review for high-stakes outputs.

### Common patterns across Phase 5

**Domain-specific chunking:**
```python
# Legal/regulatory: chunk at section headers
# Academic: chunk at paper sections
# Medical: chunk at guideline steps
# News: chunk at paragraphs
```

**Metadata filtering:**
```python
# Filter by date range for time-sensitive domains (finance, news)
results = await store.search(embedding, k=10, metadata_filter={"year": {"gte": 2023}})
```

**Confidence thresholds:**
```python
# High-stakes domains (healthcare, legal) should require high similarity scores
results = await retriever.retrieve(query, min_score=0.75)
if not results.chunks:
    return "I cannot find reliable information on this topic in my knowledge base."
```

**Resources**
- Healthcare AI guidelines: https://www.who.int/publications/i/item/9789240029200
- Legal AI considerations: https://hai.stanford.edu/
- Education AI: https://www.educause.edu/

---

## Updated Quick Reference

| Phase | Projects | Primary Tech |
|---|---|---|
| Phase 0 — Foundations | 01–05 | Python, SQL, FastAPI, Docker |
| Phase 1 — Data & Search | 06–09 | Chunking, Embeddings, pgvector, BM25 |
| Phase 2 — LLM Integration | 10–12 | Anthropic SDK, Jinja2, JSON extraction |
| Phase 3 — RAG Core | 13–15 | Full RAG pipeline, Hybrid search, RAGAS |
| Phase 4 — Production | 16–20 | Agents, Observability, Multi-tenancy, K8s |
| Phase 5 — Applications | 21–27 | Domain RAG: Cities, Education, Health... |

## Full Learning Path

```
Week 1–2:   Python Levels 1–2
Week 3:     Regex + error handling
Week 4:     SQL Levels 1–3
Week 5:     SQL Levels 4–5 (window functions, indexes)
Week 6:     FastAPI + Pydantic
Week 7:     Git + Docker
Week 8:     Text chunking + Embeddings
Week 9:     Vector databases + BM25
Week 10:    LLM APIs + Prompt engineering
Week 11:    RAG pipeline (end to end)
Week 12:    Hybrid search + Evaluation
Week 13–16: Production patterns (agents, observability, multi-tenancy)
Week 17–20: Real-world domain applications (Phase 5)
```
