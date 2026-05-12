# Employee Analytics DB

A SQLite-based employee analytics system built with pure Python stdlib. Demonstrates real-world SQL patterns including JOINs, GROUP BY, window functions, subqueries, and indexes.

## What it does

- Creates a normalized relational schema (employees, departments, locations, reviews)
- Seeds 500 realistic employees with performance reviews
- Runs 11 analytics queries covering every major SQL concept 
- Outputs results as formatted tables or JSON

## Setup

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/03-employee-analytics-db

# Initialize and seed the database
python main.py --setup
```

## Usage

```bash
# List all available queries
python main.py --list

# Run a specific query
python main.py --query headcount
python main.py --query top3
python main.py --query rank
python main.py --query reviews

# Run all queries and save to JSON
python main.py --query all --output report.json

# Use a custom DB path
python main.py --db mydb.sqlite --query headcount
```

## Available Queries

| Query | Description |
|---|---|
| `employees` | All employees with dept, manager, location |
| `headcount` | Headcount + salary stats per department |
| `remote` | Remote vs office count per department |
| `hires` | Employees hired per year |
| `rank` | Salary rank within each department |
| `top3` | Top 3 earners per department |
| `vs-avg` | Each employee salary vs dept average |
| `cumulative` | Running payroll total by hire date |
| `above-avg` | Departments above company avg salary |
| `reviews` | Employees with their latest review score |
| `review-dept` | Avg review score per department |

## Project Structure

```
employee-analytics-db/
├── main.py          # CLI entry point
├── schema.py        # Table definitions + indexes + DB connection
├── seed.py          # Fake data generator (pure stdlib)
├── queries.py       # All SQL analytics queries
├── requirements.txt
└── README.md
```

## SQL Concepts Covered

| Concept | Query |
|---|---|
| INNER JOIN + LEFT JOIN | `employees` |
| GROUP BY + HAVING | `headcount`, `above-avg` |
| Window RANK() | `rank`, `top3` |
| Window AVG() | `vs-avg` |
| Window SUM() cumulative | `cumulative` |
| Subquery in WHERE | `above-avg` |
| Correlated subquery | `reviews` |
| Multi-table JOIN | `review-dept` |
| Indexes | Defined in `schema.py` |
