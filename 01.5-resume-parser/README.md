# Resume Parser v2 — Multi-Format Support

An extended version of the Resume Parser that supports multiple file formats. Parses resumes from `.txt`, `.pdf`, `.docx`, and `.md` files into structured JSON — built with pure Python, with optional dependencies only for PDF and DOCX formats.

> **Relationship to 01-cli-resume-parser:**
> This project extends the original TXT-only parser by adding a `file_reader.py` layer that handles format detection and conversion. The core `parser.py` is unchanged — all formats are converted to plain text before parsing.

---

## What it does

- Accepts resumes in `.txt`, `.pdf`, `.docx`, and `.md` formats
- Extracts structured data: name, email, phone, location, summary, skills, experience, education
- Auto-detects file format from extension
- Outputs structured JSON to terminal or saves to file
- Supports filtering to a single section

---

## Project Structure

```
01.5-cli-resume-parser/
├── main.py               # CLI entry point (argparse)
├── parser.py             # Core ResumeParser class — unchanged from v1
├── file_reader.py        # Format dispatcher (new in v2)
├── resume_txt.txt     # Sample plain text resume
├── resume_pdf.pdf     # Sample plain text resume
├── resume_md.md      # Sample markdown resume
├── requirements.txt
└── README.md
```

### How the files relate

```
main.py
  └── file_reader.py      ← NEW: handles .txt / .md / .pdf / .docx
        └── parser.py     ← UNCHANGED: always receives plain text
```

`parser.py` has zero knowledge of file formats. `file_reader.py` converts everything to plain text first, then hands it off. This separation means you can add new formats by only touching `file_reader.py`.

---

## Setup

```bash
git clone https://github.com/yourname/rag-engineering
cd rag-engineering/01.5-cli-resume-parser

# Install dependencies (only needed for PDF and DOCX)
pip install -r requirements.txt
```

### Dependencies

| Format | Dependency | Install |
|---|---|---|
| `.txt` | None — stdlib only | — |
| `.md` | None — stdlib only | — |
| `.pdf` | `pdfplumber` | `pip install pdfplumber` |
| `.docx` | `python-docx` | `pip install python-docx` |

PDF and DOCX dependencies are lazy-loaded — if you only parse `.txt` and `.md` files, you don't need to install anything.

---

## Usage

```bash
# Parse a plain text resume
python main.py sample_resume.txt

# Parse a markdown resume
python main.py sample_resume.md

# Parse a PDF resume
python main.py resume.pdf

# Parse a Word document
python main.py resume.docx

# Save output to JSON
python main.py resume.pdf --output parsed.json

# Print only skills
python main.py resume.pdf --section skills

# Print only experience
python main.py resume.docx --section experience

# All available sections
python main.py resume.txt --section name
python main.py resume.txt --section email
python main.py resume.txt --section phone
python main.py resume.txt --section location
python main.py resume.txt --section summary
python main.py resume.txt --section skills
python main.py resume.txt --section experience
python main.py resume.txt --section education
```

---

## Example Output

```
==================================================
  RESUME PARSE SUMMARY  [PDF]
==================================================
  File       : resume.pdf
  Name       : Jane Smith
  Email      : jane.smith@email.com
  Phone      : (415) 555-0192
  Location   : San Francisco, CA
  Skills     : 10 found
  Experience : 3 role(s)
  Education  : 2 entry(s)
==================================================

{
  "name": "Jane Smith",
  "email": "jane.smith@email.com",
  "phone": "(415) 555-0192",
  "location": "San Francisco, CA",
  "summary": "Senior software engineer with 7 years of experience...",
  "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", ...],
  "experience": [...],
  "education": [...]
}
```

---

## What changed from v1

| File | Status | Change |
|---|---|---|
| `parser.py` | ✅ Unchanged | Core parsing logic untouched |
| `main.py` | 🔄 Updated | Swapped `path.read_text()` for `read_resume_file()` |
| `file_reader.py` | 🆕 New | Format detection + conversion to plain text |
| `sample_resume.md` | 🆕 New | Markdown sample for testing |
| `requirements.txt` | 🔄 Updated | Added pdfplumber + python-docx |

---

## Key Concepts Used

| Concept | Where |
|---|---|
| OOP / Classes | `ResumeParser` in `parser.py` |
| Dataclasses | `Resume` dataclass in `parser.py` |
| Regex | Email, phone, location, date extraction |
| File handling | Encoding fallback in `read_txt()` |
| Error handling | Format errors, missing deps, empty files |
| Dispatch pattern | `SUPPORTED_FORMATS` dict in `file_reader.py` |
| Lazy imports | PDF/DOCX libs imported only when needed |
| Type hints | Throughout |

