# RAG Engineering Projects

A progressive series of projects building toward a production-ready RAG (Retrieval-Augmented Generation) system. Each project introduces new concepts and builds on the last — from pure Python scripting all the way to containerized AI-powered APIs.

---
 
## Projects 

| # | Project | Concepts | Status |
|---|---------|----------|--------| 
| 01 | [Resume Parser - txt](./01-resume-parser) | Python, OOP, Regex, File I/O, JSON, argparse | ✅ Complete |
| 01.5 | [Resume Parser - pdf,docx,md,txt](./01.5-resume-parser) | Python, OOP, Regex, File I/O, JSON, argparse | ✅ Complete |
| 02 | [CSV Analyzer](./02-csv-analyzer) | Python, Classes, File I/O, Data processing | ✅ Complete |
| 03 | [Employee Analytics DB](./03-employee-analytics-db) | SQL, Joins, Window Functions, Indexes | 🔜 Coming Soon |
| 04 | [Resume Scoring API](./04-resume-scoring-api) | FastAPI, REST, Pydantic, Auth, SQLite | 🔜 Coming Soon |
| 05 | [Dockerized Resume API](./05-dockerized-resume-api) | Docker, Docker Compose, PostgreSQL, Git | 🔜 Coming Soon |

---

## Learning Path

These projects follow a structured curriculum covering the core skills needed for AI engineering:

```
Python Fundamentals
      ↓
SQL & Databases
      ↓
REST APIs with FastAPI
      ↓
Git & Docker
      ↓
RAG Systems (coming)
```

---

## How to Use This Repo

Each project lives in its own folder with:
- Its own `README.md` with setup and usage instructions
- Self-contained code — no cross-project dependencies
- A `requirements.txt` for dependencies

Navigate into any project folder and follow its README to run it independently.

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/01-cli-resume-parser
python main.py sample_resume.txt
```

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)

---

## About

Built as part of a self-directed AI engineering curriculum focused on understanding and building RAG systems from the ground up — covering every layer of the stack from data handling to deployment.
