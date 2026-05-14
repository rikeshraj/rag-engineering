"""
Analytics Queries

All SQL queries for the Employee Analytics DB.
Each function runs one query and returns results as a list of dicts.

Covers:
- Basic SELECT + JOIN
- GROUP BY + aggregates
- Window functions (via SQLite support)
- Subqueries
"""

import sqlite3
from pathlib import Path

from schema import get_connection, DB_PATH


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert sqlite3.Row objects to plain dicts."""
    return [dict(row) for row in rows]


# ------------------------------------------------------------------
# 1. Basic SELECT + JOIN
# ------------------------------------------------------------------

def get_all_employees(db_path: Path = DB_PATH) -> list[dict]:
    """
    List all employees with their department name, manager name,
    and office city.

    Concepts: INNER JOIN, LEFT JOIN, aliases, multi-table join
    """
    sql = """
        SELECT
            e.id,
            e.name,
            e.email,
            e.job_title,
            d.name          AS department,
            l.city          AS office_city,
            m.name          AS manager_name,
            e.salary,
            e.hire_date,
            CASE e.is_remote WHEN 1 THEN 'Yes' ELSE 'No' END AS remote
        FROM employees e
        JOIN  departments d ON e.department_id = d.id
        JOIN  locations   l ON d.location_id   = l.id
        LEFT JOIN employees m ON e.manager_id  = m.id
        ORDER BY e.name
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def get_employees_by_department(department: str, db_path: Path = DB_PATH) -> list[dict]:
    """
    Filter employees by department name.
    Demonstrates parameterized queries (safe from SQL injection).
    """
    sql = """
        SELECT e.name, e.job_title, e.salary, e.hire_date
        FROM   employees e
        JOIN   departments d ON e.department_id = d.id
        WHERE  d.name = ?
        ORDER  BY e.salary DESC
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql, (department,)).fetchall())


# ------------------------------------------------------------------
# 2. GROUP BY + aggregates
# ------------------------------------------------------------------

def headcount_and_salary_by_department(db_path: Path = DB_PATH) -> list[dict]:
    """
    Headcount, average salary, min/max salary per department.

    Concepts: GROUP BY, COUNT, AVG, MIN, MAX, HAVING
    """
    sql = """
        SELECT
            d.name                          AS department,
            COUNT(e.id)                     AS headcount,
            ROUND(AVG(e.salary), 2)         AS avg_salary,
            MIN(e.salary)                   AS min_salary,
            MAX(e.salary)                   AS max_salary,
            SUM(e.salary)                   AS total_payroll
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        GROUP BY d.name
        HAVING COUNT(e.id) > 0
        ORDER BY avg_salary DESC
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def remote_vs_office_by_department(db_path: Path = DB_PATH) -> list[dict]:
    """
    Count of remote vs office employees per department.

    Concepts: GROUP BY multiple columns, conditional COUNT
    """
    sql = """
        SELECT
            d.name  AS department,
            COUNT(CASE WHEN e.is_remote = 1 THEN 1 END) AS remote_count,
            COUNT(CASE WHEN e.is_remote = 0 THEN 1 END) AS office_count,
            COUNT(e.id)                                  AS total
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        GROUP BY d.name
        ORDER BY total DESC
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def hires_per_year(db_path: Path = DB_PATH) -> list[dict]:
    """
    Number of employees hired each year.

    Concepts: GROUP BY with string function (SUBSTR for year extraction)
    """
    sql = """
        SELECT
            SUBSTR(hire_date, 1, 4)  AS year,
            COUNT(*)                 AS hires
        FROM employees
        GROUP BY year
        ORDER BY year
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


# ------------------------------------------------------------------
# 3. Window functions
# ------------------------------------------------------------------

def salary_rank_by_department(db_path: Path = DB_PATH) -> list[dict]:
    """
    Rank each employee by salary within their department.

    Concepts: RANK() OVER (PARTITION BY ... ORDER BY ...)
    """
    sql = """
        SELECT
            e.name,
            d.name                                              AS department,
            e.salary,
            RANK() OVER (
                PARTITION BY e.department_id
                ORDER BY e.salary DESC
            )                                                   AS dept_salary_rank
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        ORDER BY department, dept_salary_rank
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def top3_earners_per_department(db_path: Path = DB_PATH) -> list[dict]:
    """
    Top 3 earners in each department.

    Concepts: Window function inside a subquery, filtering on rank
    """
    sql = """
        SELECT name, department, salary, dept_salary_rank
        FROM (
            SELECT
                e.name,
                d.name AS department,
                e.salary,
                RANK() OVER (
                    PARTITION BY e.department_id
                    ORDER BY e.salary DESC
                ) AS dept_salary_rank
            FROM employees e
            JOIN departments d ON e.department_id = d.id
        )
        WHERE dept_salary_rank <= 3
        ORDER BY department, dept_salary_rank
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def salary_vs_department_average(db_path: Path = DB_PATH) -> list[dict]:
    """
    Each employee's salary compared to their department average.

    Concepts: AVG() as window function, arithmetic on window results
    """
    sql = """
        SELECT
            e.name,
            d.name                                          AS department,
            e.salary,
            ROUND(AVG(e.salary) OVER (
                PARTITION BY e.department_id
            ), 2)                                           AS dept_avg_salary,
            ROUND(e.salary - AVG(e.salary) OVER (
                PARTITION BY e.department_id
            ), 2)                                           AS diff_from_avg
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        ORDER BY department, diff_from_avg DESC
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def cumulative_payroll_by_hire_date(db_path: Path = DB_PATH) -> list[dict]:
    """
    Running total of salary spend ordered by hire date.

    Concepts: SUM() OVER (ORDER BY ...) — cumulative/running window
    """
    sql = """
        SELECT
            hire_date,
            name,
            salary,
            ROUND(SUM(salary) OVER (
                ORDER BY hire_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ), 2) AS running_payroll_total
        FROM employees
        ORDER BY hire_date
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


# ------------------------------------------------------------------
# 4. Subqueries
# ------------------------------------------------------------------

def departments_above_company_avg_salary(db_path: Path = DB_PATH) -> list[dict]:
    """
    Departments whose average salary exceeds the company-wide average.

    Concepts: Subquery in WHERE clause
    """
    sql = """
        SELECT
            d.name                  AS department,
            ROUND(AVG(e.salary), 2) AS avg_salary
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        GROUP BY d.name
        HAVING AVG(e.salary) > (
            SELECT AVG(salary) FROM employees
        )
        ORDER BY avg_salary DESC
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def employees_with_latest_review(db_path: Path = DB_PATH) -> list[dict]:
    """
    Each employee with their most recent performance review score.

    Concepts: Correlated subquery, MAX() in subquery
    """
    sql = """
        SELECT
            e.name,
            d.name      AS department,
            e.salary,
            pr.score    AS latest_review_score,
            pr.review_date
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        JOIN performance_reviews pr ON pr.employee_id = e.id
        WHERE pr.review_date = (
            SELECT MAX(review_date)
            FROM performance_reviews
            WHERE employee_id = e.id
        )
        ORDER BY latest_review_score DESC
        LIMIT 50
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())


def avg_review_score_by_department(db_path: Path = DB_PATH) -> list[dict]:
    """
    Average performance review score per department.

    Concepts: JOIN across 3 tables, GROUP BY with aggregate on joined table
    """
    sql = """
        SELECT
            d.name                      AS department,
            COUNT(DISTINCT e.id)        AS employees_reviewed,
            ROUND(AVG(pr.score), 2)     AS avg_review_score,
            MIN(pr.score)               AS lowest_score,
            MAX(pr.score)               AS highest_score
        FROM performance_reviews pr
        JOIN employees   e ON pr.employee_id   = e.id
        JOIN departments d ON e.department_id  = d.id
        GROUP BY d.name
        ORDER BY avg_review_score DESC
    """
    with get_connection(db_path) as conn:
        return rows_to_dicts(conn.execute(sql).fetchall())
