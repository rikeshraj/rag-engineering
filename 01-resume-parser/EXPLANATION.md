# CLI Resume Parser — File-by-File Breakdown

A complete explanation of every file in the project, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
01-cli-resume-parser/
├── main.py             # CLI entry point
├── parser.py           # Core parsing logic
├── sample_resume.txt   # Sample resume for testing
├── requirements.txt
└── README.md
```

---

## `parser.py`

### What it does
Contains two things: the `Resume` dataclass that holds parsed data, and the `ResumeParser` class that does the actual parsing. Every other file in the project either feeds text into `ResumeParser` or reads from a `Resume` object.

### The `Resume` dataclass

```python
@dataclass
class Resume:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    raw_text: str = ""
```

**Why a dataclass instead of a plain dict?**
A dataclass gives you a structured object with named attributes, a free `__init__`, and type hints — without the boilerplate of writing `__init__` yourself. Accessing `resume.email` is cleaner and less error-prone than `resume["email"]`. It also makes the shape of parsed data explicit and self-documenting.

**Why `field(default_factory=list)` for list fields?**
In Python, mutable default arguments are shared across all instances. Writing `skills: list = []` would make every `Resume` object share the same list — adding a skill to one would add it to all. `field(default_factory=list)` creates a fresh list for each instance.

### The `ResumeParser` class

**Why a class instead of standalone functions?**
The regex patterns (`EMAIL_PATTERN`, `PHONE_PATTERN`, etc.) and section headers are shared state used across multiple methods. Putting them on a class as class variables means they're compiled once and reused — not recompiled on every function call. It also makes the parser easy to extend: subclass and override just the patterns you want to change.

**`_split_into_sections()`**
This is the most important method. It walks through lines top to bottom and groups them under section headers:

```
Line: "Jane Smith"          → bucket: "header"
Line: "jane@email.com"      → bucket: "header"
Line: "Skills"              → detected as section header
Line: "Python, FastAPI"     → bucket: "skills"
Line: "Experience"          → detected as section header
Line: "Senior Engineer..."  → bucket: "experience"
```

The key insight: section headers are detected by exact match against the `SECTION_HEADERS` dict (case-insensitive, stripped). Everything between two headers belongs to the first one.

**`_extract_name()` heuristic**
There's no reliable way to detect a name with regex alone — names don't follow a fixed pattern. Instead, the first non-empty line in the top 5 lines that has no email, no digits, and no more than 5 words is treated as the name. This works for the vast majority of real resumes where the name is the first line.

**`_parse_skills()`**
Skills can be formatted many ways across different resumes:
- `Python, FastAPI, Docker` (comma separated)
- `Python | FastAPI | Docker` (pipe separated)
- `• Python` (bullet per line)

The method splits on all common delimiters at once using `re.split(r"[,|•·\-]\s*", line)` then cleans each part. `dict.fromkeys()` is used to deduplicate while preserving order — `set()` would lose order.

**`_parse_experience()` date detection**
Experience entries are identified by looking for date patterns (`January 2021`, `Mar 2019`) — these almost always mark the start of a new role. Everything after a date line until the next blank line or date line is treated as bullets for that role.

---

## `main.py`

### What it does
The CLI entry point. Reads a file, calls the parser, and prints or saves the result. Contains no parsing logic — it's purely about input/output and user experience.

### Key decisions

**`argparse` for CLI**
Python's `argparse` stdlib module handles all flag parsing. Defining arguments declaratively (`add_argument`) is cleaner than manually parsing `sys.argv`. It also auto-generates `--help` output.

**`--section` flag**
Instead of always printing the full JSON, `--section skills` prints just the skills list. This makes the tool composable — you can pipe output: `python main.py resume.txt --section skills | sort`.

**Errors go to `stderr`, output goes to `stdout`**
Error messages use `file=sys.stderr` so they don't pollute the actual data output. This matters when piping: `python main.py resume.txt | jq .skills` — if errors went to stdout, `jq` would choke on them.

**`print_summary_banner()` before JSON**
A quick human-readable summary is printed before the raw JSON so you immediately see whether the parse worked without reading the full output. The JSON follows for machine consumption.

**Encoding fallback in `read_resume()`**
Tries `utf-8` first, then falls back to `latin-1`. Real-world files often use different encodings depending on where they were created. Failing with an unhelpful `UnicodeDecodeError` instead of trying a fallback is bad UX.

---

## `requirements.txt`

The entire parser uses Python stdlib only: `re`, `json`, `argparse`, `pathlib`, `dataclasses`. No external libraries means:
- No `pip install` needed to run the parser
- No version conflicts
- No security surface from third-party packages
