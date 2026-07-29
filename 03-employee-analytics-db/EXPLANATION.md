# Employee Analytics DB — File-by-File Breakdown

A complete explanation of every file in the project, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
03-employee-analytics-db/
├── main.py          # CLI entry point + query registry
├── schema.py        # Table definitions + indexes + DB connection
├── seed.py          # Fake data generator
├── queries.py       # All SQL analytics queries
├── requirements.txt
└── README.md
```

### How the files connect

```
main.py
  ├── schema.py   ← get_connection() used by all files
  ├── seed.py     ← populates DB (calls schema.py)
  └── queries.py  ← all analytics (calls schema.py)
```

`schema.py` is the foundation every other file imports. `queries.py` and `seed.py` never talk to each other — they both go through `schema.py` for DB access.

---

## `schema.py`

### What it does
Three things: defines the SQL schema, creates the connection helper, and provides `init_db()` to set everything up.

### Schema design — 4 normalized tables

```
locations
    ↑
departments  (location_id → locations.id)
    ↑
employees    (department_id → departments.id)
             (manager_id   → employees.id)  ← self-referencing
    ↑
performance_reviews  (employee_id → employees.id)
```

**Why normalize instead of one big table?**
If department names and city were stored directly on each employee row, updating "New York" to "New York City" would require updating every row for every employee in that city. Normalization stores city once in `locations` — one update propagates everywhere. This is the core reason relational databases exist.

**Self-referencing foreign key on `employees`**
```sql
manager_id INTEGER REFERENCES employees(id)
```
A manager is also an employee. The `manager_id` column points back to the same table. This is called a self-join and is a common pattern for hierarchical data (org charts, categories, file systems).

**`is_remote INTEGER DEFAULT 0`**
SQLite has no native boolean type — it stores everything as text, integer, or real. `0` and `1` are used to represent false and true. In queries this is handled with `CASE WHEN is_remote = 1 THEN 'Yes' ELSE 'No' END`.

**`IF NOT EXISTS` on all creates**
`CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` make `init_db()` idempotent — safe to call on every startup. Running it twice doesn't duplicate tables or fail with an error.

### `get_connection()`

```python
def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

**`row_factory = sqlite3.Row`**
Without this, query results are plain tuples: `row[3]`. With it, columns are accessible by name: `row["salary"]`. Every file in the project uses `get_connection()` so this setting applies everywhere automatically.

**`PRAGMA foreign_keys = ON`**
SQLite ignores foreign key constraints by default — it stores the FK relationship in the schema but doesn't enforce it at runtime. This pragma turns enforcement on per connection. Without it, you could insert an employee with a `department_id` that doesn't exist and SQLite wouldn't complain.

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department_id);
CREATE INDEX IF NOT EXISTS idx_employees_manager    ON employees(manager_id);
CREATE INDEX IF NOT EXISTS idx_employees_hire_date  ON employees(hire_date);
CREATE INDEX IF NOT EXISTS idx_reviews_employee     ON performance_reviews(employee_id);
```

**Which columns to index and why:**
- `department_id` — most queries JOIN or filter on this
- `manager_id` — self-join for manager names
- `hire_date` — used in range queries and ORDER BY
- `employee_id` on reviews — every review query joins on this

**Why not index everything?**
Indexes speed up reads but slow down writes — every INSERT or UPDATE must also update the index. Over-indexing a write-heavy table creates more overhead than benefit.

---

## `seed.py`

### What it does
Populates the database with 500 realistic fake employees, managers, and performance reviews — using only the Python stdlib.

### Insertion order — why it matters

```python
def seed():
    _clear_tables(conn)       # 1. clear in reverse FK order
    location_ids = _seed_locations(conn)    # 2. no dependencies
    dept_ids = _seed_departments(conn, location_ids)  # 3. needs locations
    emp_ids = _seed_employees(conn, dept_ids, 500)    # 4. needs depts
    _seed_managers(conn, dept_ids, emp_ids)           # 5. needs emp IDs
    _seed_reviews(conn, emp_ids)                      # 6. needs emp IDs
```

**Why managers are set in a second pass (`_seed_managers`)**
When inserting employee 1, employee 2 doesn't exist yet — you can't reference an ID that hasn't been created. The solution: insert all employees first with `manager_id = NULL`, then go back and update each one with a random manager ID from the now-complete set. This is the standard approach for seeding hierarchical data.

**`_clear_tables()` — reverse FK order**
```python
conn.executescript("""
    DELETE FROM performance_reviews;
    DELETE FROM employees;
    DELETE FROM departments;
    DELETE FROM locations;
""")
```
With foreign keys enforced, you can't delete a department while employees still reference it. Tables must be cleared in reverse dependency order — children before parents.

**`unique_email()` — collision handling**
```python
def unique_email(name, used):
    base = name.lower().replace(" ", ".")
    email = f"{base}@company.com"
    counter = 1
    while email in used:
        email = f"{base}{counter}@company.com"
        counter += 1
    used.add(email)
    return email
```
Tracks used emails in a `set` for O(1) lookups. On collision, appends an incrementing counter. This mirrors how real systems handle duplicate usernames.

**`random_review_date()` — realistic dates**
Reviews are guaranteed to be at least 6 months after hire date. Without this constraint, you'd get reviews on the same day as hire — unrealistic and potentially confusing for analytics queries.

---

## `queries.py`

### What it does
Contains all 11 analytics queries, each as a standalone function that returns `list[dict]`. Every function follows the same pattern: open connection → execute SQL → return results.

### `rows_to_dicts()`

```python
def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]
```

Converts `sqlite3.Row` objects to plain Python dicts. This means query results can be serialized to JSON, passed to formatters, or used in tests without any special handling.

### Query breakdown by SQL concept

**Multi-table JOIN — `get_all_employees()`**
```sql
FROM employees e
JOIN  departments d ON e.department_id = d.id
JOIN  locations   l ON d.location_id   = l.id
LEFT JOIN employees m ON e.manager_id  = m.id
```
Uses `LEFT JOIN` for the manager because `manager_id` can be `NULL` — an `INNER JOIN` would exclude employees with no manager. The self-join aliases the same table twice (`e` for employee, `m` for manager).

**GROUP BY + HAVING — `headcount_and_salary_by_department()`**
```sql
GROUP BY d.name
HAVING COUNT(e.id) > 0
```
`HAVING` filters after grouping (unlike `WHERE` which filters before). Used here to exclude empty departments. Every column in `SELECT` is either in `GROUP BY` or wrapped in an aggregate — this is SQL's fundamental GROUP BY rule.

**Window RANK() — `salary_rank_by_department()`**
```sql
RANK() OVER (PARTITION BY e.department_id ORDER BY e.salary DESC)
```
`PARTITION BY` resets the rank counter for each department. `ORDER BY DESC` ranks highest salary as 1. Unlike `GROUP BY`, window functions don't collapse rows — every employee row remains, just with a rank column added.

**Why `top3` uses a subquery**
```sql
SELECT name, department, salary, dept_salary_rank
FROM (
    SELECT ..., RANK() OVER (...) AS dept_salary_rank
    FROM employees ...
)
WHERE dept_salary_rank <= 3
```
You can't filter on a window function result in the same `WHERE` clause where it's computed — the window hasn't been evaluated yet at that stage. The inner query computes ranks for all employees; the outer query filters to top 3. This is a standard SQL pattern.

**Running total — `cumulative_payroll_by_hire_date()`**
```sql
SUM(salary) OVER (
    ORDER BY hire_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)
```
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` means "sum all rows from the very first row up to and including the current row." This is what makes it cumulative — each row's value includes all previous rows.

**Correlated subquery — `employees_with_latest_review()`**
```sql
WHERE pr.review_date = (
    SELECT MAX(review_date)
    FROM performance_reviews
    WHERE employee_id = e.id  ← references outer query
)
```
The inner `SELECT` references `e.id` from the outer query — it runs once per outer row. This finds the most recent review for each employee without needing window functions.

---

## `main.py`

### What it does
CLI with three modes: `--setup` (init + seed), `--query <name>` (run one or all queries), and `--list` (show available queries).

### The query registry pattern

```python
QUERY_REGISTRY = {
    "headcount": (queries.headcount_and_salary_by_department, "description"),
    "top3":      (queries.top3_earners_per_department,        "description"),
    ...
}
```

A dict maps CLI names to `(function, description)` tuples. Benefits:
- Adding a new query = one line in the dict, zero changes to CLI logic
- `--list` iterates the dict automatically
- `--query all` iterates and calls every function
- No `if/elif` chain to maintain

**`print_table()` — dynamic column widths**
Column widths are calculated by scanning all rows for the longest value in each column. This ensures the table stays aligned regardless of data length — no hardcoded widths that break with long values.
