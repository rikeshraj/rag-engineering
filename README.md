# RAG Engineering Projects

A progressive series of projects building toward a production-ready RAG (Retrieval-Augmented Generation) system. Each project introduces new concepts and builds on the last — from pure Python scripting all the way to real-world AI applications across industries.

---

## Projects

### Phase 0 — Foundations

| # | Project | Concepts | Status |
|---|---------|----------|--------|
| 01 | [Resume Parser (TXT)](./01-resume-parser) | Python, OOP, Regex, File I/O, JSON, argparse | ✅ Complete |
| 01.5 | [Resume Parser (PDF, DOCX, MD, TXT)](./01.5-resume-parser) | Multi-format parsing, Dispatch pattern, Unicode handling | ✅ Complete |
| 02 | [CSV Analyzer](./02-csv-analyzer) | Statistics from scratch, Type detection, Pure Python math | ✅ Complete |
| 03 | [Employee Analytics DB](./03-employee-analytics-db) | SQL, Joins, Window Functions, Indexes, SQLite | ✅ Complete |
| 04 | [Resume Scoring API](./04-resume-scoring-api) | FastAPI, REST, Pydantic, Auth, SQLite | ✅ Complete |
| 05 | [Dockerized Resume API](./05-dockerized-resume-api) | Docker, Docker Compose, PostgreSQL, psycopg2 | ✅ Complete |

---

### Phase 1 — Data & Search

| # | Project | Concepts | Status |
|---|---------|----------|--------|
| 06 | [Document Chunker](./06-document-chunker) | Fixed, Sentence, Recursive & Token chunking strategies | ✅ Complete |
| 07 | [Embedding Service](./07-embedding-service) | OpenAI embeddings, Async batch, Caching, Cosine similarity | ✅ Complete |
| 08 | [Vector Store API](./08-vector-store-api) | pgvector, HNSW index, Cosine search, Collections | ✅ Complete |
| 09 | [BM25 Search Engine](./09-bm25-search-engine) | Inverted index, TF-IDF, BM25 formula, Stemming, Stopwords | ✅ Complete |

---

### Phase 2 — LLM Integration

| # | Project | Concepts | Status |
|---|---------|----------|--------|
| 10 | [LLM Gateway](./10-llm-gateway) | Anthropic SDK, Streaming SSE, Retry + backoff, Token tracking | ✅ Complete |
| 11 | [Prompt Engineering Toolkit](./11-prompt-toolkit) | Jinja2 templates, Few-shot, Chain-of-thought, HyDE, Chains | ✅ Complete |
| 12 | [Structured Output Extractor](./12-structured-extractor) | JSON extraction, Retry on failure, Type coercion, Confidence scoring | ✅ Complete |

---

### Phase 3 — RAG Core

| # | Project | Concepts | Status |
|---|---------|----------|--------|
| 13 | [Basic RAG Pipeline](./13-rag-pipeline) | Ingest → Embed → Store → Retrieve → Generate, Citations | ✅ Complete |
| 14 | [Hybrid Search RAG](./14-hybrid-rag) | BM25 + Vector search, Reciprocal Rank Fusion, Reranking | 🔄 In Progress |
| 15 | [RAG Evaluation Framework](./15-rag-evaluation) | Faithfulness, Relevance, RAGAS metrics, Benchmarking | 🔜 Coming Soon |

---

### Phase 4 — Production RAG

| # | Project | Concepts | Status |
|---|---------|----------|--------|
| 16 | [Agentic RAG](./16-agentic-rag) | Tool use, Multi-hop retrieval, Query rewriting, ReAct | 🔜 Coming Soon |
| 17 | [RAG with Observability](./17-rag-observability) | Structured logging, Tracing, Latency, Cost per query | 🔜 Coming Soon |
| 18 | [Multi-tenant RAG API](./18-multi-tenant-rag) | Per-user namespaces, JWT, Rate limiting, Billing hooks | 🔜 Coming Soon |
| 19 | [Full-stack RAG App](./19-fullstack-rag) | React frontend, WebSocket streaming, File upload, Chat UI | 🔜 Coming Soon |
| 20 | [Production RAG System](./20-production-rag) | CI/CD, Kubernetes, Auto-scaling, Monitoring, Full deployment | 🔜 Coming Soon |

---

### Phase 5 — Real-World RAG Applications

Applying everything built in Phases 0–4 to solve real industry problems. Each project uses a full RAG stack applied to a specific domain — ingesting domain data, building specialised retrieval, and surfacing intelligent answers.

| # | Project | Domain | Status |
|---|---------|--------|--------|
| 21 | [Smart City Application](./21-smart-city-rag) | Urban infrastructure, civic services, city planning queries | 🔜 Coming Soon |
| 22 | [Education & Research](./22-education-rag) | Academic papers, curricula, personalised learning assistants | 🔜 Coming Soon |
| 23 | [Transport & Logistics](./23-transport-rag) | Routes, schedules, regulations, fleet management queries | 🔜 Coming Soon |
| 24 | [Leisure & Self Development](./24-leisure-rag) | Fitness, hobbies, personal growth, recommendation engine | 🔜 Coming Soon |
| 25 | [Housing Market](./25-housing-rag) | Property listings, market trends, mortgage, legal documents | 🔜 Coming Soon |
| 26 | [Energy Sector](./26-energy-rag) | Grid data, renewables, regulations, sustainability reports | 🔜 Coming Soon |
| 27 | [Healthcare](./27-healthcare-rag) | Clinical notes, drug interactions, research papers, triage | 🔜 Coming Soon |

---

## Learning Path

```
Phase 0: Python · SQL · FastAPI · Docker
             ↓
Phase 1: Chunking · Embeddings · Vector Search · BM25
             ↓
Phase 2: LLM APIs · Prompt Engineering · Structured Extraction
             ↓
Phase 3: RAG Pipeline · Hybrid Search · Evaluation
             ↓
Phase 4: Agents · Observability · Multi-tenancy · Production
             ↓
Phase 5: Real-World Applications across Industries
```

---

## How to Use This Repo

Each project lives in its own folder with:
- `README.md` — setup and usage instructions
- `EXPLANATION.md` — file-by-file breakdown of every decision made
- Self-contained code — no cross-project dependencies
- `requirements.txt` for dependencies
- `tests/` folder (optional, clearly separated)

Navigate into any project folder and follow its README:

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/13-rag-pipeline
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![pgvector](https://img.shields.io/badge/pgvector-latest-orange)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude-purple)
![Jinja2](https://img.shields.io/badge/Jinja2-3.1+-red)

---

## Project Stats

| Phase | Projects | Complete | In Progress | Coming Soon |
|---|---|---|---|---|
| Phase 0 — Foundations | 6 | 6 | 0 | 0 |
| Phase 1 — Data & Search | 4 | 4 | 0 | 0 |
| Phase 2 — LLM Integration | 3 | 3 | 0 | 0 |
| Phase 3 — RAG Core | 3 | 1 | 1 | 1 |
| Phase 4 — Production RAG | 5 | 0 | 0 | 5 |
| Phase 5 — Applications | 7 | 0 | 0 | 7 |
| **Total** | **28** | **14** | **1** | **13** |

---

## About

Built as part of a self-directed AI engineering curriculum focused on understanding and building RAG systems from the ground up — covering every layer of the stack from data handling to production deployment and real-world domain applications.

> Each project is fully documented with an `EXPLANATION.md` that covers every design decision, the reasoning behind each choice, and the key concepts demonstrated — making this repo a learning resource as much as a codebase.
