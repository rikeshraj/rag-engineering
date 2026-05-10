# Resume Parser

A tool that parses plain-text resumes into structured JSON. Built with pure Python stdlib — no external dependencies except `pytest` for testing.

## What it does

- Extracts contact info (name, email, phone, location)
- Parses sections: summary, skills, experience, education
- Outputs structured JSON to terminal or file
- Supports filtering to a single section
 
## Usage

```bash 
# Parse and print full result
python main.py sample_resume.txt
 
# Save output to file
python main.py sample_resume.txt --output result.json

# Print only skills
python main.py sample_resume.txt --section skills

# Print only experience
python main.py sample_resume.txt --section experience

# Compact JSON output
python main.py sample_resume.txt --format json
```

## Run Tests

```bash
python -m pytest tests.py -v
```

## Project Structure

```
resume-parser/
├── main.py             # Terminal entry point (argparse)
├── parser.py           # ResumeParser class + Resume dataclass
├── sample_resume.txt   # Example resume for testing
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| Dataclasses | `Resume` dataclass in `parser.py` |
| OOP / Classes | `ResumeParser` class with private methods |
| Regex | Email, phone, location, date extraction |
| File handling | `Path.read_text()` in `main.py` |
| JSON | `json.dumps` / `json.loads` output |
| Error handling | File not found, encoding errors, permission errors |
| CLI with argparse | `build_arg_parser()` in `main.py` |
| Type hints | Throughout |
