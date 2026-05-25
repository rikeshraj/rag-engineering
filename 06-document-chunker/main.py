"""
Document Chunker — CLI Entry Point

Usage:
    python main.py document.txt
    python main.py document.txt --strategy sentence
    python main.py document.txt --strategy recursive --chunk-size 256 --overlap 30
    python main.py document.txt --output chunks.json
    python main.py document.txt --compare
"""

import argparse
import json
import sys
from pathlib import Path

from chunker import get_chunker, STRATEGIES, ChunkResult


# ------------------------------------------------------------------
# File reader (supports txt, md, pdf, docx)
# ------------------------------------------------------------------

def read_file(path: Path) -> str:
    """Read a document file and return plain text."""
    ext = path.suffix.lower()

    if ext in (".txt", ".md", ""):
        for enc in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode '{path}'")

    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            print("Install pdfplumber: pip install pdfplumber", file=sys.stderr)
            sys.exit(1)
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=2, y_tolerance=3, use_text_flow=True)
                if words:
                    lines: dict[float, list[str]] = {}
                    for w in words:
                        top = round(w["top"], 1)
                        lines.setdefault(top, []).append(w["text"])
                    pages.append("\n".join(" ".join(v) for v in lines.values()))
        return "\n\n".join(pages)

    if ext == ".docx":
        try:
            from docx import Document
        except ImportError:
            print("Install python-docx: pip install python-docx", file=sys.stderr)
            sys.exit(1)
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    raise ValueError(f"Unsupported format '{ext}'. Use: .txt .md .pdf .docx")


# ------------------------------------------------------------------
# Formatting
# ------------------------------------------------------------------

def print_summary(result: ChunkResult) -> None:
    """Print a summary table of the chunking result."""
    print(f"\n{'=' * 60}")
    print(f"  CHUNKING SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Source       : {result.source}")
    print(f"  Strategy     : {result.strategy}")
    print(f"  Chunk size   : {result.chunk_size} chars")
    print(f"  Overlap      : {result.chunk_overlap} chars")
    print(f"  Total chars  : {result.total_chars:,}")
    print(f"  Total chunks : {result.total_chunks}")
    print(f"  Avg chunk    : {result.avg_chunk_size} chars")
    print(f"{'=' * 60}\n")


def print_chunks(result: ChunkResult, max_preview: int = 80) -> None:
    """Print each chunk with its metadata."""
    for chunk in result.chunks:
        preview = chunk.text[:max_preview].replace("\n", " ")
        if len(chunk.text) > max_preview:
            preview += "..."
        print(f"  [{chunk.index:>3}] chars {chunk.start_char:>6}–{chunk.end_char:<6} "
              f"~{chunk.token_estimate:>4} tokens | {preview}")


def print_comparison(text: str, source: str, chunk_size: int, overlap: int) -> None:
    """Run all strategies and compare their output stats."""
    print(f"\n{'=' * 60}")
    print(f"  STRATEGY COMPARISON  (chunk_size={chunk_size}, overlap={overlap})")
    print(f"{'=' * 60}")
    print(f"  {'Strategy':<12} {'Chunks':>8} {'Avg size':>10} {'Min':>8} {'Max':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*8} {'-'*8}")

    for name in ["fixed", "sentence", "recursive"]:
        try:
            chunker = get_chunker(name, chunk_size=chunk_size, chunk_overlap=overlap, source=source)
            result = chunker.chunk(text)
            sizes = [len(c.text) for c in result.chunks]
            print(
                f"  {name:<12} {result.total_chunks:>8} "
                f"{result.avg_chunk_size:>10.1f} "
                f"{min(sizes):>8} {max(sizes):>8}"
            )
        except Exception as e:
            print(f"  {name:<12} {'error':>8}  {e}")

    print()


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="document-chunker",
        description="Split a document into chunks ready for embedding.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py doc.txt
  python main.py doc.txt --strategy sentence --chunk-size 256
  python main.py doc.txt --strategy recursive --overlap 30
  python main.py doc.txt --output chunks.json
  python main.py doc.txt --compare
  python main.py doc.txt --show-chunks
        """,
    )
    parser.add_argument("file", type=Path, help="Document to chunk (.txt .md .pdf .docx)")
    parser.add_argument(
        "--strategy", "-s",
        choices=list(STRATEGIES.keys()),
        default="recursive",
        help="Chunking strategy (default: recursive)",
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int, default=512,
        help="Max characters per chunk (default: 512)",
    )
    parser.add_argument(
        "--overlap", "-ov",
        type=int, default=50,
        help="Overlap between chunks in characters (default: 50)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path, default=None,
        help="Save chunks as JSON to this file",
    )
    parser.add_argument(
        "--show-chunks",
        action="store_true",
        help="Print each chunk preview to terminal",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run all strategies and compare results",
    )
    return parser


def main() -> None:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args()

    if not args.file.exists():
        print(f"Error: '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        text = read_file(args.file)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("Error: document is empty.", file=sys.stderr)
        sys.exit(1)

    # Compare mode
    if args.compare:
        print_comparison(text, args.file.name, args.chunk_size, args.overlap)
        return

    # Single strategy mode
    try:
        chunker = get_chunker(
            args.strategy,
            chunk_size=args.chunk_size,
            chunk_overlap=args.overlap,
            source=args.file.name,
        )
        result = chunker.chunk(text)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print_summary(result)

    if args.show_chunks:
        print_chunks(result)

    if args.output:
        try:
            args.output.write_text(
                json.dumps(result.to_dict(), indent=2),
                encoding="utf-8",
            )
            print(f"Saved to {args.output}", file=sys.stderr)
        except PermissionError:
            print(f"Error: cannot write to '{args.output}'", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
