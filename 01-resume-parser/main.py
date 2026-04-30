"""
Resume Parser - Entry Point

Usage:
    python main.py resume.txt
    python main.py resume.txt --output result.json
    python main.py resume.txt --format pretty
    python main.py resume.txt --section skills
"""

import argparse
import json
import sys
from pathlib import Path

from parser import ResumeParser


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-parser",
        description="Parse a plain-text resume into structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py resume.txt
  python main.py resume.txt --output parsed.json
  python main.py resume.txt --format pretty
  python main.py resume.txt --section skills
  python main.py resume.txt --section experience
        """,
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the resume .txt file",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Save output to a JSON file (optional)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "pretty"],
        default="pretty",
        help="Output format: 'json' (compact) or 'pretty' (indented, default)",
    )
    parser.add_argument(
        "--section", "-s",
        choices=["name", "email", "phone", "location", "summary", "skills", "experience", "education"],
        default=None,
        help="Print only a specific section",
    )
    return parser


def read_resume(path: Path) -> str:
    # Read resume file, with clear error messages.
    if not path.exists():
        print(f"Error: File '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    if path.suffix.lower() not in (".txt", ".md", ""):
        print(
            f"Warning: '{path.suffix}' files may not parse correctly. "
            "Plain .txt files work best.",
            file=sys.stderr,
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback for files with different encodings
        return path.read_text(encoding="latin-1")
    except PermissionError:
        print(f"Error: No permission to read '{path}'.", file=sys.stderr)
        sys.exit(1)


def format_pretty(data: dict) -> str:
    # Format the parsed resume as readable indented JSON.
    return json.dumps(data, indent=2)


def print_section(data: dict, section: str) -> None:
    # Print just one section of the parsed resume.
    value = data.get(section)
    if value is None:
        print(f"Section '{section}' not found.", file=sys.stderr)
        sys.exit(1)

    if isinstance(value, list):
        if not value:
            print(f"No {section} found.")
        elif isinstance(value[0], dict):
            # List of dicts (experience, education)
            print(json.dumps(value, indent=2))
        else:
            # List of strings (skills)
            for item in value:
                print(f"  • {item}")
    else:
        print(value)


def save_output(data: dict, path: Path) -> None:
    # Save parsed data to a JSON file.
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved to {path}", file=sys.stderr)
    except PermissionError:
        print(f"Error: No permission to write to '{path}'.", file=sys.stderr)
        sys.exit(1)


def print_summary_banner(data: dict) -> None:
    # Print a quick human-readable summary before the JSON.
    print("\n" + "=" * 50)
    print("  RESUME PARSE SUMMARY")
    print("=" * 50)
    print(f"  Name       : {data.get('name') or '—'}")
    print(f"  Email      : {data.get('email') or '—'}")
    print(f"  Phone      : {data.get('phone') or '—'}")
    print(f"  Location   : {data.get('location') or '—'}")
    print(f"  Skills     : {len(data.get('skills', []))} found")
    print(f"  Experience : {len(data.get('experience', []))} role(s)")
    print(f"  Education  : {len(data.get('education', []))} entry(s)")
    print("=" * 50 + "\n")


def main() -> None:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args()

    # 1. Read the file
    raw_text = read_resume(args.file)

    # 2. Parse
    resume_parser = ResumeParser()
    resume = resume_parser.parse(raw_text)
    data = resume.to_dict()

    # 3. Output
    if args.section:
        # Single section mode
        print_section(data, args.section)
    else:
        # Full output
        print_summary_banner(data)
        formatted = format_pretty(data)
        print(formatted)

    # 4. Optionally save to file
    if args.output:
        save_output(data, args.output)


if __name__ == "__main__":
    main()
