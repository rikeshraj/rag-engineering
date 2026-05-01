"""
CSV Analyzer - CLI Entry Point

Usage:
    python main.py data.csv
    python main.py data.csv --output report.json
    python main.py data.csv --column salary
    python main.py data.csv --correlations
    python main.py data.csv --missing
    python main.py data.csv --top 10
"""

import argparse
import json
import sys
from pathlib import Path

from analyzer import CSVAnalyzer


# ──────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────

def print_banner(result) -> None:
    print("\n" + "=" * 55)
    print("  CSV ANALYSIS REPORT")
    print("=" * 55)
    print(f"  File         : {result.file_name}")
    print(f"  Rows         : {result.total_rows:,}")
    print(f"  Columns      : {result.total_columns}")
    print(f"  Headers      : {', '.join(result.headers)}")
    print("=" * 55)


def print_column(col) -> None:
    print(f"\n  [{col.dtype.upper()}] {col.name}")
    print(f"    Count   : {col.count:,}  |  Missing: {col.missing}")
    if col.dtype == "numeric":
        print(f"    Mean    : {col.mean}")
        print(f"    Median  : {col.median}")
        print(f"    Min     : {col.minimum}  |  Max: {col.maximum}")
        print(f"    Std Dev : {col.std_dev}")
    else:
        print(f"    Unique  : {col.unique_count}")
        print(f"    Top values:")
        for val, count in col.top_values:
            bar = "█" * min(int((count / col.count) * 30), 30)
            print(f"      {str(val):<20} {bar} {count}")


def print_missing_report(result) -> None:
    print("\n── MISSING VALUES REPORT ──")
    has_missing = False
    for col in result.columns:
        if col.missing > 0:
            pct = (col.missing / result.total_rows) * 100
            print(f"  {col.name:<25} {col.missing:>5} missing  ({pct:.1f}%)")
            has_missing = True
    if not has_missing:
        print("  No missing values found ✓")


def print_correlations(result) -> None:
    if not result.correlations:
        return
    cols = list(result.correlations.keys())
    print("\n── CORRELATION MATRIX ──")
    # Header row
    print(f"  {'':20}", end="")
    for c in cols:
        print(f"  {c[:10]:>10}", end="")
    print()
    # Data rows
    for row_col in cols:
        print(f"  {row_col[:20]:<20}", end="")
        for col_col in cols:
            val = result.correlations[row_col].get(col_col)
            print(f"  {val:>10.3f}" if val is not None else f"  {'N/A':>10}", end="")
        print()


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-analyzer",
        description="Analyze a CSV file and print summary statistics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py data.csv
  python main.py data.csv --output report.json
  python main.py data.csv --column salary
  python main.py data.csv --correlations
  python main.py data.csv --missing
  python main.py data.csv --top 10
        """,
    )
    parser.add_argument("file", type=Path, help="Path to the CSV file")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Save full report as JSON")
    parser.add_argument("--column", "-c", default=None,
                        help="Show stats for a single column only")
    parser.add_argument("--correlations", action="store_true",
                        help="Compute and show correlation matrix")
    parser.add_argument("--missing", action="store_true",
                        help="Show missing values report only")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of top values for categorical columns (default: 5)")
    return parser


def main() -> None:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args()

    # Run analysis
    try:
        analyzer = CSVAnalyzer(args.file, top_n=args.top)
        result = analyzer.analyze(correlations=args.correlations)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Output modes ──

    if args.missing:
        # Just the missing report
        print_banner(result)
        print_missing_report(result)

    elif args.column:
        # Single column
        match = next((c for c in result.columns if c.name == args.column), None)
        if not match:
            print(f"Error: Column '{args.column}' not found.", file=sys.stderr)
            print(f"Available columns: {', '.join(result.headers)}", file=sys.stderr)
            sys.exit(1)
        print_banner(result)
        print_column(match)

    else:
        # Full report
        print_banner(result)
        for col in result.columns:
            print_column(col)
        print_missing_report(result)
        if args.correlations:
            print_correlations(result)

    print()

    # Save to file if requested
    if args.output:
        try:
            args.output.write_text(
                json.dumps(result.to_dict(), indent=2), encoding="utf-8"
            )
            print(f"Report saved to {args.output}", file=sys.stderr)
        except PermissionError:
            print(f"Error: Cannot write to {args.output}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
