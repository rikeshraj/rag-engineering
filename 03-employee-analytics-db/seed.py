"""
Seed Script

Populates the database with realistic fake employee data.
Uses only the Python stdlib — no faker library needed.

Run: python seed.py
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from schema import get_connection, init_db, DB_PATH


# ------------------------------------------------------------------
# Fake data pools
# ------------------------------------------------------------------

FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Karen", "Leo", "Mia", "Noah", "Olivia", "Paul",
    "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zane", "Amy", "Brian", "Chloe", "Derek", "Elena", "Felix",
    "Gina", "Harry", "Isla", "Jake", "Kylie", "Liam", "Maya", "Nathan",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Young", "Robinson", "Clark",
    "Lewis", "Walker", "Hall", "Allen", "King", "Wright", "Hill", "Lopez",
]

DEPARTMENTS = {
    "Engineering":  {"city": "New York",      "min_salary": 90000,  "max_salary": 220000},
    "Marketing":    {"city": "San Francisco",  "min_salary": 60000,  "max_salary": 140000},
    "Sales":        {"city": "Chicago",        "min_salary": 55000,  "max_salary": 160000},
    "Finance":      {"city": "New York",       "min_salary": 75000,  "max_salary": 200000},
    "HR":           {"city": "Chicago",        "min_salary": 50000,  "max_salary": 120000},
    "Data Science": {"city": "San Francisco",  "min_salary": 100000, "max_salary": 230000},
}

JOB_TITLES = {
    "Engineering":  ["Junior Engineer", "Software Engineer", "Senior Engineer",
                     "Staff Engineer", "Principal Engineer", "CTO"],
    "Marketing":    ["Content Writer", "SEO Specialist", "Marketing Manager",
                     "Marketing Director", "CMO"],
    "Sales":        ["Sales Rep", "Account Executive", "Sales Manager",
                     "VP of Sales", "Chief Revenue Officer"],
    "Finance":      ["Financial Analyst", "Senior Analyst", "Finance Manager",
                     "VP of Finance", "CFO"],
    "HR":           ["HR Coordinator", "HR Specialist", "HR Manager",
                     "VP of HR", "Chief People Officer"],
    "Data Science": ["Data Analyst", "Data Scientist", "Senior Data Scientist",
                     "ML Engineer", "Head of Data", "Chief Data Officer"],
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def random_date(start_year: int = 2015, end_year: int = 2024) -> str:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")


def random_review_date(hire_date: str) -> str:
    """Return a review date that's at least 6 months after hire."""
    hired = date.fromisoformat(hire_date)
    earliest = hired + timedelta(days=180)
    today = date.today()
    if earliest >= today:
        return today.strftime("%Y-%m-%d")
    delta = (today - earliest).days
    return (earliest + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")


def unique_email(name: str, used: set) -> str:
    base = name.lower().replace(" ", ".")
    email = f"{base}@company.com"
    counter = 1
    while email in used:
        email = f"{base}{counter}@company.com"
        counter += 1
    used.add(email)
    return email


# ------------------------------------------------------------------
# Seeding
# ------------------------------------------------------------------

def seed(db_path: Path = DB_PATH, num_employees: int = 500) -> None:
    init_db(db_path)

    with get_connection(db_path) as conn:
        _clear_tables(conn)
        location_ids = _seed_locations(conn)
        dept_ids = _seed_departments(conn, location_ids)
        emp_ids = _seed_employees(conn, dept_ids, num_employees)
        _seed_managers(conn, dept_ids, emp_ids)
        _seed_reviews(conn, emp_ids)

    print(f"Seeded {num_employees} employees with reviews into '{db_path}'")


def _clear_tables(conn: sqlite3.Connection) -> None:
    """Clear in reverse FK order to avoid constraint violations."""
    conn.executescript("""
        DELETE FROM performance_reviews;
        DELETE FROM employees;
        DELETE FROM departments;
        DELETE FROM locations;
    """)


def _seed_locations(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert cities, return {city: id}."""
    cities = list({v["city"] for v in DEPARTMENTS.values()})
    ids = {}
    for city in cities:
        cur = conn.execute(
            "INSERT INTO locations (city, country) VALUES (?, ?)", (city, "US")
        )
        ids[city] = cur.lastrowid
    return ids


def _seed_departments(conn: sqlite3.Connection, location_ids: dict) -> dict[str, int]:
    """Insert departments, return {dept_name: id}."""
    ids = {}
    for dept, info in DEPARTMENTS.items():
        cur = conn.execute(
            "INSERT INTO departments (name, location_id) VALUES (?, ?)",
            (dept, location_ids[info["city"]]),
        )
        ids[dept] = cur.lastrowid
    return ids


def _seed_employees(
    conn: sqlite3.Connection,
    dept_ids: dict[str, int],
    count: int,
) -> dict[int, str]:
    """
    Insert employees, return {employee_id: hire_date}.
    Manager IDs are set in a second pass to avoid FK issues.
    """
    used_emails: set = set()
    used_names: set = set()
    emp_ids: dict[int, str] = {}

    dept_names = list(DEPARTMENTS.keys())

    for _ in range(count):
        # Unique full name
        for _ in range(10):
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break

        dept = random.choice(dept_names)
        dept_info = DEPARTMENTS[dept]
        title = random.choice(JOB_TITLES[dept])
        salary = round(random.uniform(dept_info["min_salary"], dept_info["max_salary"]), 2)
        hire_date = random_date()
        is_remote = random.choice([0, 0, 1])  # 33% remote
        email = unique_email(name, used_emails)

        cur = conn.execute(
            """INSERT INTO employees
               (name, email, job_title, department_id, salary, hire_date, is_remote)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, email, title, dept_ids[dept], salary, hire_date, is_remote),
        )
        emp_ids[cur.lastrowid] = hire_date

    return emp_ids


def _seed_managers(
    conn: sqlite3.Connection,
    dept_ids: dict[str, int],
    emp_ids: dict[int, str],
) -> None:
    """Assign a random manager from the same department to each employee."""
    all_emp_ids = list(emp_ids.keys())
    for emp_id in all_emp_ids:
        # Pick any other employee as manager
        possible = [e for e in all_emp_ids if e != emp_id]
        if possible:
            manager_id = random.choice(possible)
            conn.execute(
                "UPDATE employees SET manager_id = ? WHERE id = ?",
                (manager_id, emp_id),
            )


def _seed_reviews(
    conn: sqlite3.Connection,
    emp_ids: dict[int, str],
) -> None:
    """Give each employee 1-3 performance reviews."""
    all_ids = list(emp_ids.keys())
    for emp_id, hire_date in emp_ids.items():
        num_reviews = random.randint(1, 3)
        for _ in range(num_reviews):
            reviewer_id = random.choice([e for e in all_ids if e != emp_id])
            conn.execute(
                """INSERT INTO performance_reviews
                   (employee_id, review_date, score, reviewer_id, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    emp_id,
                    random_review_date(hire_date),
                    round(random.uniform(2.5, 5.0), 1),
                    reviewer_id,
                    random.choice([
                        "Consistently meets expectations",
                        "Exceeds targets regularly",
                        "Strong team player",
                        "Shows great initiative",
                        "Needs improvement in communication",
                        "Excellent technical skills",
                        "Great leadership potential",
                        None,
                    ]),
                ),
            )


if __name__ == "__main__":
    seed()
