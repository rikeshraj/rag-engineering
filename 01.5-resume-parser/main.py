import argparse
import json
import sys
from pathlib import Path

from file_reader import read_resume_file, SUPPORTED_FORMATS
from parser import ResumeParser


def build_arg_parser() -> argparse.ArgumentParser:
    supported = ", ".join(SUPPORTED_FORMATS.keys())
    parser = argparse.ArgumentParser(
        prog="resume-parser",
        description=f"Parse a resume into structured JSON. Supports: {supported}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py resume.txt
  python main.py resume.pdf
  python main.py resume.docx
  python main.py resume.md
  python main.py resume.pdf --output parsed.json
  python main.py resume.pdf --section skills
  python main.py resume.pdf --section experience
        """,
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the resume file (.txt, .md, .pdf, .docx)",
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
        choices=["name", "email", "phone", "location", "summary",
                 "skills", "experience", "education"],
        default=None,
        help="Print only a specific section",
    )
    return parser


def print_section(data: dict, section: str) -> None:
    """Print just one section of the parsed resume."""
    value = data.get(section)
    if value is None:
        print(f"Section '{section}' not found.", file=sys.stderr)
        sys.exit(1)

    if isinstance(value, list):
        if not value:
            print(f"No {section} found.")
        elif isinstance(value[0], dict):
            print(json.dumps(value, indent=2))
        else:
            for item in value:
                print(f"  • {item}")
    else:
        print(value)


def save_output(data: dict, path: Path) -> None:
    """Save parsed data to a JSON file."""
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved to {path}", file=sys.stderr)
    except PermissionError:
        print(f"Error: No permission to write to '{path}'.", file=sys.stderr)
        sys.exit(1)


def print_summary_banner(data: dict, file_path: Path) -> None:
    """Print a quick human-readable summary before the JSON."""
    ext = file_path.suffix.upper().lstrip(".")
    print("\n" + "=" * 50)
    print(f"  RESUME PARSE SUMMARY  [{ext}]")
    print("=" * 50)
    print(f"  File       : {file_path.name}")
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

    # 1. Read the file (handles all formats)
    try:
        raw_text = read_resume_file(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Parse
    resume_parser = ResumeParser()
    resume = resume_parser.parse(raw_text)
    data = resume.to_dict()

    # 3. Output
    if args.section:
        print_section(data, args.section)
    else:
        print_summary_banner(data, args.file)
        print(json.dumps(data, indent=2))

    # 4. Optionally save to file
    if args.output:
        save_output(data, args.output)


if __name__ == "__main__":
    main()
