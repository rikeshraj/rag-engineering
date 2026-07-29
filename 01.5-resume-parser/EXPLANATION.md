# CLI Resume Parser v2 (Multi-Format) — File-by-File Breakdown

A complete explanation of every file in the project, what changed from v1, and the key decisions made.

---

## Project Structure

```
01.5-cli-resume-parser/
├── main.py             # CLI entry point (updated)
├── parser.py           # Core parsing logic (unchanged from v1)
├── file_reader.py      # Format dispatcher (new)
├── sample_resume.txt   # Plain text sample
├── sample_resume.md    # Markdown sample (new)
├── requirements.txt    # Updated with pdfplumber + python-docx
└── README.md
```

### How the files connect

```
main.py
  └── file_reader.py     ← NEW: handles format detection + conversion
        └── parser.py    ← UNCHANGED: always receives plain text
```

`parser.py` has zero knowledge that multiple formats exist. `file_reader.py` converts everything to plain text first. This is the **single responsibility principle** — each file does one thing.

---

## `file_reader.py` (new)

### What it does
Detects the file format from the extension, reads it using the appropriate library, converts it to plain text, and normalizes Unicode characters — all before the parser ever sees the text.

### The dispatch pattern

```python
SUPPORTED_FORMATS = {
    ".txt":  read_txt,
    ".md":   read_markdown,
    ".pdf":  read_pdf,
    ".docx": read_docx,
}

def read_resume_file(path: Path) -> str:
    ext = path.suffix.lower()
    reader = SUPPORTED_FORMATS[ext]
    text = reader(path)
    text = _normalize_unicode(text)
    return text
```

A dict maps extensions to reader functions. Adding a new format is one line in the dict — no `if/elif` chain to update. This is the **dispatch pattern** and is common in production parsers and plugin systems.

### `read_txt()` — encoding fallback

```python
ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
```

Tries encodings in order. Real-world files are created on different operating systems with different default encodings. Windows commonly produces `cp1252`, older systems produce `latin-1`. Trying a list of encodings instead of hardcoding one prevents silent failures.

### `read_markdown()` — regex stripping

Markdown headers (`## Skills`), bold markers (`**text**`), links (`[text](url)`), and bullets (`- item`) are all removed or normalized using regex. The result is plain text that the existing parser can handle without modification.

Key regex patterns used:
- `re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)` — strip headers
- `re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)` — strip bold/italic, keep text
- `re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)` — strip links, keep label

### `read_pdf()` — word-based extraction

**Why `extract_words()` instead of `extract_text()`?**
PDFs store characters at absolute X/Y coordinates — there's no concept of "space between words" in the file format. `extract_text()` often misses spaces. `extract_words()` groups characters into words using bounding boxes first, then we reconstruct lines manually — more reliable.

```python
words = page.extract_words(
    x_tolerance=2,      # gap threshold for inserting spaces
    y_tolerance=3,      # gap threshold for new lines
    use_text_flow=True, # follow reading order, not raw coordinates
)
```

**`_words_to_text()`**
Groups words into lines by comparing their vertical position (`top`). Two words within 3 points vertically are on the same line. Lines are joined with spaces, lines are joined with newlines.

### `_normalize_unicode()` — Unicode cleanup

PDFs embed characters using font-specific codepoints that have no meaning outside the original font. Four categories are cleaned:

| Category | Example | Fix |
|---|---|---|
| Dashes | `\u2013` (en dash) | Replace with `-` |
| Bullets | `\uf0b7` (PDF private use) | Replace with `•` |
| Spaces | `\u00a0` (non-breaking) | Replace with regular space |
| Private use area `\ue000–\uf8ff` | Garbage glyphs | Strip entirely |

`unicodedata.normalize("NFC")` at the end combines base characters with their accents into single codepoints — so `café` stays `café` rather than becoming `cafe` + a floating accent mark.

### `_fix_spacing()` — spacing cleanup

Three passes after Unicode normalization:

1. **CamelCase split** — `re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", text)` splits `SoftwareEngineer` into `Software Engineer`. Only triggers at lowercase→uppercase boundaries, leaving acronyms like `APIs` and `AWS` intact.

2. **Post-punctuation space** — `re.sub(r"([,|•])([^\s])", r"\1 \2", text)` inserts a space after commas and bullets that directly touch the next word.

3. **Multiple space collapse** — `re.sub(r"[^\S\n]+", " ", text)` collapses multiple spaces into one while preserving newlines.

### `read_docx()` — paragraph extraction

`python-docx` provides `doc.paragraphs` — a list of paragraph objects each with a `.text` attribute. Empty paragraphs are filtered out. The result is joined with newlines.

**Why not extract table text?**
Some resumes use tables for layout. This version skips table cells for simplicity. Extending it would mean iterating `doc.tables` and extracting `cell.text` from each row.

### Lazy imports

```python
def read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        print("Install with: pip install pdfplumber")
        sys.exit(1)
```

`pdfplumber` and `python-docx` are imported inside their respective functions, not at the top of the file. This means if you only parse `.txt` and `.md` files, you don't need to install either library — the tool works out of the box without them.

---

## `parser.py` — education parser rewrite

The only file that changed from v1 (besides `main.py`). The `_parse_education()` method was rewritten to handle PDF-style bullet formats.

**Problem:** PDFs often format education as a single bullet line:
```
• Guru Nanak Institute of Technology, Kolkata  July 2019 - June 2023
• B.Tech in Computer Science and Engineering
```

The original parser expected separate lines for degree, institution, and year. It couldn't handle inline dates or consecutive bullets where institution and degree are split across two bullets.

**Fix — retroactive degree attachment:**
```python
# PRE-CHECK at top of loop
if has_degree and not has_date and not has_institution:
    if entries and entries[-1]["institution"] and not entries[-1]["degree"]:
        entries[-1]["degree"] = cleaned
        continue
```

When a degree-only bullet is encountered, it checks if the last appended entry already has an institution but no degree. If so, it attaches the degree retroactively instead of creating a new entry. This handles the consecutive bullet pattern without needing lookahead.

**Noise filter:**
```python
noise_patterns = re.compile(
    r"(relocation|hybrid|remote|open to|declaration|hereby|certify)",
    re.IGNORECASE
)
entries = [e for e in entries if not noise_patterns.search(...)]
```

Sections like "Additional Information" that appear after Education in PDFs sometimes bleed into the education bucket. The noise filter strips entries whose text matches common footer patterns.

---

## `main.py` — one change

```python
# Before (v1)
raw_text = path.read_text(encoding="utf-8")

# After (v1.5)
raw_text = read_resume_file(args.file)
```

That's the only change to `main.py`. The rest of the file is identical. This demonstrates clean separation — adding four new file formats required touching exactly one line in the CLI.

---

## `requirements.txt`

```
pdfplumber>=0.10.0    # PDF text extraction
python-docx>=1.0.0   # Word document parsing
pytest>=7.0           # Optional: testing
```

`pdfplumber` and `python-docx` are the only additions. Both are well-maintained libraries with active communities. `psycopg2`, `pandas`, and `numpy` are deliberately avoided — this project stays as lightweight as possible.
