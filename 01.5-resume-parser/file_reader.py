import re
import sys
from pathlib import Path


# ------------------------------------------------------------------
# Format readers
# ------------------------------------------------------------------

def read_txt(path: Path) -> str:
    """Read plain text file with encoding fallback."""
    for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode '{path}' with any supported encoding.")


def read_markdown(path: Path) -> str:
    """
    Read a markdown resume and strip markdown syntax.
    Converts headers, bullets, bold/italic into plain text
    so the parser can process it normally.
    """
    raw = read_txt(path)

    # Remove markdown headers (# ## ###) but keep the text
    text = re.sub(r"^#{1,6}\s+", "", raw, flags=re.MULTILINE)

    # Remove bold/italic markers (**text** / *text* / __text__ / _text_)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)

    # Remove markdown links [text](url) → text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)

    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove HTML tags (sometimes present in .md files)
    text = re.sub(r"<[^>]+>", "", text)

    # Normalize bullet points (-, *, +) to plain bullets
    text = re.sub(r"^[\*\-\+]\s+", "• ", text, flags=re.MULTILINE)

    return text.strip()


def read_pdf(path: Path) -> str:
    """
    Extract text from a PDF resume using pdfplumber.

    PDFs store characters at absolute X/Y coordinates — they have no
    concept of "spaces between words". pdfplumber has to infer spaces
    from the gaps between character positions.

    We use extract_text() with explicit x_tolerance and y_tolerance
    settings to control when pdfplumber decides two characters are
    "far enough apart" to insert a space or a newline between them.

    x_tolerance: max horizontal gap (in PDF points) before inserting
                 a space. Lower = more spaces inserted. Default is 3.
                 We use 2 to catch tighter-spaced fonts.

    y_tolerance: max vertical gap before treating chars as a new line.
                 We use 3 (default) — works well for most resumes.

    After extraction we also run a post-processing pass to catch any
    remaining "smashedwords" by inserting spaces before capital letters
    that directly follow lowercase letters mid-word (CamelCase boundary),
    which is a common artifact in columnar or styled PDFs.
    """
    try:
        import pdfplumber
    except ImportError:
        print(
            "Error: 'pdfplumber' is required for PDF support.\n"
            "Install it with: pip install pdfplumber",
            file=sys.stderr,
        )
        sys.exit(1)

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # Use word-based extraction first — pdfplumber assembles
            # words from individual characters using bounding boxes,
            # then joins them with spaces. More reliable than raw chars.
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=True,   # follow reading order, not raw coords
            )

            if words:
                text = _words_to_text(words)
            else:
                # Fallback to extract_text if no words found
                text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""

            if text.strip():
                pages.append(text.strip())

    if not pages:
        raise ValueError(
            f"Could not extract any text from '{path}'. "
            "The PDF may be scanned or image-based."
        )

    raw = "\n\n".join(pages)
    return _fix_spacing(raw)


def _words_to_text(words: list[dict]) -> str:
    """
    Convert pdfplumber word objects back to readable text.

    Each word dict has: text, x0, top, x1, bottom.
    We group words into lines by their vertical position (top),
    then join each line's words with spaces.
    """
    if not words:
        return ""

    # Group words into lines based on vertical position
    # Two words are on the same line if their tops are within 3 points
    lines: list[list[str]] = []
    current_line: list[str] = []
    current_top = words[0]["top"]

    for word in words:
        if abs(word["top"] - current_top) <= 3:
            current_line.append(word["text"])
        else:
            if current_line:
                lines.append(current_line)
            current_line = [word["text"]]
            current_top = word["top"]

    if current_line:
        lines.append(current_line)

    return "\n".join(" ".join(line) for line in lines)


def _normalize_unicode(text: str) -> str:
    """
    Replace common Unicode characters that PDFs use for bullets,
    dashes, quotes, and symbols with clean ASCII equivalents.

    PDFs embed these as special Unicode codepoints (e.g. \u2022 for
    bullet, \u2013 for en-dash) which look fine in a PDF viewer but
    show up as raw escape sequences when extracted as text.
    """
    replacements = {
        # Dashes
        "\u2013": "-",   # en dash
        "\u2014": "-",   # em dash
        "\u2015": "-",   # horizontal bar
        "\u2212": "-",   # minus sign

        # Bullets and list markers
        "\u2022": "•",   # bullet •
        "\u2023": "•",   # triangular bullet
        "\u25aa": "•",   # small black square
        "\u25cf": "•",   # black circle
        "\u2024": "•",   # one dot leader
        "\uf0b7": "•",   # common PDF bullet (private use area)

        # Quotes
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote

        # Spaces
        "\u00a0": " ",   # non-breaking space
        "\u200b": "",    # zero-width space (remove entirely)
        "\u200c": "",    # zero-width non-joiner
        "\u200d": "",    # zero-width joiner
        "\ufeff": "",    # byte order mark (BOM)

        # Symbols
        "\u2022": "•",   # bullet
        "\u00b7": "•",   # middle dot
        "\u2027": "•",   # hyphenation point
        "\u00e2": "",    # common PDF garbled char artifact
    }

    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)

    # Catch any remaining non-ASCII characters that are pure garbage
    # (private use area \ue000–\uf8ff — these are font-specific glyphs
    #  that have no meaning outside the original PDF font)
    text = re.sub(r"[\ue000-\uf8ff]", "", text)

    # Normalize to NFC form — combines base characters with their
    # accents/diacritics into single codepoints (é instead of e + ́)
    import unicodedata
    text = unicodedata.normalize("NFC", text)

    return text


def _fix_spacing(text: str) -> str:
    """
    Post-processing pass to fix common PDF spacing artifacts.

    1. Normalize Unicode escape characters (bullets, dashes, quotes)
    2. Insert space at lowercase→UPPERCASE boundaries mid-word
    3. Collapse multiple spaces into one
    4. Fix run-together words after punctuation
    """
    # Step 1: normalize Unicode first before any other processing
    text = _normalize_unicode(text)

    # Step 2: fix camelCase boundaries that aren't intentional acronyms
    # Only insert space when: lowercase letter followed by uppercase + more chars
    text = re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", text)

    # Step 3: fix run-together words after punctuation (comma, pipe, bullet)
    text = re.sub(r"([,|•])([^\s])", r"\1 \2", text)

    # Step 4: collapse multiple spaces into one (but preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)

    # Step 5: remove spaces that crept in at start of lines
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)

    return text


def read_docx(path: Path) -> str:
    """
    Extract text from a Word (.docx) resume using python-docx.
    Preserves paragraph structure.
    """
    try:
        from docx import Document
    except ImportError:
        print(
            "Error: 'python-docx' is required for DOCX support.\n"
            "Install it with: pip install python-docx",
            file=sys.stderr,
        )
        sys.exit(1)

    doc = Document(str(path))
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        raise ValueError(f"Could not extract any text from '{path}'.")

    return "\n".join(paragraphs)


# ------------------------------------------------------------------
# Main dispatcher
# ------------------------------------------------------------------

SUPPORTED_FORMATS = {
    ".txt":  read_txt,
    ".md":   read_markdown,
    ".pdf":  read_pdf,
    ".docx": read_docx,
}


def read_resume_file(path: Path) -> str:
    """
    Read a resume file and return its content as plain text.
    Dispatches to the correct reader based on file extension.

    Raises:
        FileNotFoundError — file doesn't exist
        ValueError        — unsupported format or empty content
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: '{path}'")

    ext = path.suffix.lower()

    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise ValueError(
            f"Unsupported format '{ext}'. Supported formats: {supported}"
        )

    reader = SUPPORTED_FORMATS[ext]
    text = reader(path)

    if not text.strip():
        raise ValueError(f"No text content found in '{path}'.")

    # Always normalize unicode regardless of format —
    # bullets, dashes, and special chars can appear in any file type
    text = _normalize_unicode(text)

    return text
