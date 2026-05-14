"""
Employee Analytics DB - CLI Entry Point

Usage:
    python main.py --setup                        # init + seed DB
    python main.py --query headcount              # run a specific query
    python main.py --query top3                   # top 3 earners per dept
    python main.py --list                         # list available queries
    python main.py --query all --output report.json
"""

import argparse
import json
import sys
from pathlib import Path

import queries
from schema import DB_PATH, init_db
from seed import seed


# ------------------------------------------------------------------
# Query registry — maps CLI name → (function, description)
# ------------------------------------------------------------------

QUERY_REGISTRY = {
    "employees":    (queries.get_all_employees,                  "All employees with dept, manager, location"),
    "headcount":    (queries.headcount_and_salary_by_department, "Headcount + salary stats per department"),
    "remote":       (queries.remote_vs_office_by_department,     "Remote vs office count per department"),
    "hires":        (queries.hires_per_year,                     "Employees hired per year"),
    "rank":         (queries.salary_rank_by_department,          "Salary rank within each department"),
    "top3":         (queries.top3_earners_per_department,        "Top 3 earners per department"),
    "vs-avg":       (queries.salary_vs_department_average,       "Each employee salary vs dept average"),
    "cumulative":   (queries.cumulative_payroll_by_hire_date,    "Running payroll total by hire date"),
    "above-avg":    (queries.departments_above_company_avg_salary,"Departments above company avg salary"),
    "reviews":      (queries.employees_with_latest_review,       "Employees with their latest review score"),
    "review-dept":  (queries.avg_review_score_by_department,     "Avg review score per department"),
}


def build_arg_parser() -> argparse.ArgumentParser:
    query_names = list(QUERY_REGISTRY.keys()) + ["all"]
    parser = argparse.ArgumentParser(
        prog="employee-analytics",
        description="Run SQL analytics queries on the Employee DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --setup
  python main.py --list
  python main.py --query headcount
  python main.py --query top3
  python main.py --query all --output report.json
        """,
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Initialize and seed the database",
    )
    parser.add_argument(
        "--query", "-q",
        choices=query_names,
        help="Query to run (or 'all' to run every query)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Save results as JSON to this file",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available queries",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Path to SQLite database file (default: {DB_PATH})",
    )
    return parser


def print_table(rows: list[dict], max_rows: int = 20) -> None:
    """Print results as a formatted table."""
    if not rows:
        print("  (no results)")
        return

    displayed = rows[:max_rows]
    headers = list(displayed[0].keys())

    # Calculate column widths
    col_widths = {h: len(str(h)) for h in headers}
    for row in displayed:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(str(row.get(h, ""))))

    # Header row
    header_line = "  " + " | ".join(str(h).ljust(col_widths[h]) for h in headers)
    separator   = "  " + "-+-".join("-" * col_widths[h] for h in headers)
    print(header_line)
    print(separator)

    for row in displayed:
        line = "  " + " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
        print(line)

    if len(rows) > max_rows:
        print(f"\n  ... and {len(rows) - max_rows} more rows (showing first {max_rows})")


def run_query(name: str, db_path: Path) -> list[dict]:
    """Run a named query and return results."""
    fn, description = QUERY_REGISTRY[name]
    print(f"\n{'=' * 60}")
    print(f"  {name.upper()} — {description}")
    print(f"{'=' * 60}")
    results = fn(db_path)
    print_table(results)
    print(f"\n  Total rows: {len(results)}")
    return results


def list_queries() -> None:
    print("\nAvailable queries:\n")
    for name, (_, description) in QUERY_REGISTRY.items():
        print(f"  {name:<15} {description}")
    print(f"\n  {'all':<15} Run all queries")


def main() -> None:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args()

    if not any([args.setup, args.query, args.list]):
        arg_parser.print_help()
        sys.exit(0)

    # List mode
    if args.list:
        list_queries()
        return

    # Setup mode
    if args.setup:
        print("Initializing and seeding database...")
        seed(db_path=args.db)
        return

    # Check DB exists before querying
    if not args.db.exists():
        print(f"Error: Database '{args.db}' not found. Run --setup first.", file=sys.stderr)
        sys.exit(1)

    # Query mode
    all_results = {}

    if args.query == "all":
        for name in QUERY_REGISTRY:
            all_results[name] = run_query(name, args.db)
    else:
        all_results[args.query] = run_query(args.query, args.db)

    # Save to JSON if requested
    if args.output:
        try:
            args.output.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
            print(f"\nResults saved to {args.output}")
        except PermissionError:
            print(f"Error: Cannot write to '{args.output}'", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
