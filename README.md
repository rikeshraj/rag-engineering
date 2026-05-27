# RAG Engineering Projects

A progressive series of projects building toward a production-ready RAG (Retrieval-Augmented Generation) system. Each project introduces new concepts and builds on the last — from pure Python scripting all the way to containerized AI-powered APIs.

---
 
## Projects 

| # | Project | Concepts | Status | 
|---|---------|----------|--------| 
| | Phase 0 | Foundations |
| 01 | [Resume Parser - txt](./01-resume-parser) | Python, OOP, Regex, File I/O, JSON, argparse | ✅ Complete | 
| 01.5 | [Resume Parser - pdf,docx,md,txt](./01.5-resume-parser) | Python, OOP, Regex, File I/O, JSON, argparse | ✅ Complete | 
| 02 | [CSV Analyzer](./02-csv-analyzer) | Python, Classes, File I/O, Data processing | ✅ Complete | 
| 03 | [Employee Analytics DB](./03-employee-analytics-db) | SQL, Joins, Window Functions, Indexes | ✅ Complete | 
| 04 | [Resume Scoring API](./04-resume-scoring-api) | FastAPI, REST, Pydantic, Auth, SQLite | ✅ Complete | 
| 05 | [Dockerized Resume API](./05-dockerized-resume-api) | Docker, Docker Compose, PostgreSQL, Git | ✅ Complete | 
| | Phase 1 | Data & Search |
| 06 | [Document Chunker](./06-document-chunker) | Text splitting, Overlap, Token counting, Multiple strategies | ✅ Complete | 
| 07 | [Embedding Service](./07-embedding-service) | OpenAI / HuggingFace embeddings, Async, Batch processing | ✅ Complete | 
| 08 | [Vector Store API](./08-vector-store-api) | pgvector, Cosine similarity, HNSW index, FastAPI | ✅ Complete | 
| 09 | [BM25 Search Engine](./09-bm25-search-engine) | Keyword search, TF-IDF, Inverted index, Pure Python | 🔜 Coming Soon | 
| | Phase 2 | LLM Integration |
| 10 | [LLM Gateway API](./10-llm-gateway-api) | Anthropic / OpenAI SDK, Streaming, Retry logic, Token tracking | 🔜 Coming Soon | 
| 11 | [Prompt Engineering Toolkit](./11-prompt-engineering-toolkit) | Prompt templates, Few-shot, Chain-of-thought, Jinja2 | 🔜 Coming Soon | 
| 12 | [Structured Output Extractor](./12-structured-output-extractor) | JSON mode, Pydantic + LLM, Function calling, Validation | 🔜 Coming Soon | 
| | Phase 3 | RAG Core | 🔜 Coming Soon |
| | Phase 4 | Production RAG | 🔜 Coming Soon |

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
