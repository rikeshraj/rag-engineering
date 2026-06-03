# BM25 Search Engine

A keyword search engine built from scratch in pure Python — no Elasticsearch, no Solr, no external search libraries. Implements the BM25 ranking algorithm with an inverted index, stopword filtering, and stemming, exposed as a FastAPI service.

## What it does

- Index documents with tokenization, stopword removal, and stemming
- Search with BM25 ranking — shows which terms matched and their scores
- Filter search by collection namespace
- Persist and restore the index to/from disk (auto-saves on shutdown)
- Full CRUD on indexed documents

## Why BM25 matters for RAG

Vector search is great for semantic similarity but misses exact keyword matches. If a user searches for a specific model name, error code, or product ID, BM25 finds it reliably. Hybrid RAG (Project 14) combines BM25 + vector search to get the best of both.

## Setup

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/09-bm25-search-engine

pip install -r requirements.txt
cp .env.example .env

uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for the Swagger UI.

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Health check + index size |
| POST | `/documents` | ✅ | Index one document |
| POST | `/documents/batch` | ✅ | Index many documents |
| GET | `/documents/{id}` | ✅ | Get document by ID |
| DELETE | `/documents/{id}` | ✅ | Remove from index |
| POST | `/search` | ✅ | BM25 keyword search |
| GET | `/stats` | ✅ | Index statistics |
| POST | `/index/save` | ✅ | Save index to disk |
| POST | `/index/load` | ✅ | Load index from disk |
| DELETE | `/index` | ✅ | Clear entire index |

---

## Usage

### Index a document

```bash
curl -X POST http://localhost:8000/documents \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"content": "BM25 is the standard ranking algorithm used by Elasticsearch.", "collection": "search_docs"}'
```

### Search

```bash
curl -X POST http://localhost:8000/search \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "ranking algorithm elasticsearch", "k": 5}'
```

**Response:**
```json
{
  "query": "ranking algorithm elasticsearch",
  "query_tokens": ["rank", "algorithm", "elasticsearch"],
  "returned": 1,
  "results": [
    {
      "doc_id": 1,
      "score": 3.421,
      "matched_terms": ["rank", "algorithm", "elasticsearch"],
      "content": "BM25 is the standard ranking algorithm used by Elasticsearch."
    }
  ]
}
```

---

## How BM25 works

```
score(D, Q) = Σ IDF(qᵢ) × f(qᵢ, D) × (k1 + 1)
                          ─────────────────────────────────────
                          f(qᵢ,D) + k1 × (1 - b + b × |D|/avgdl)
```

| Parameter | Default | Meaning |
|---|---|---|
| `k1` | 1.5 | Term frequency saturation. Higher = more weight on repetition |
| `b` | 0.75 | Length normalization. 0=none, 1=full |

Configurable via environment variables `BM25_K1` and `BM25_B`.

---

## Project Structure

```
09-bm25-search-engine/
├── main.py          # FastAPI routes
├── engine.py        # SearchEngine — ties everything together
├── bm25.py          # BM25 scoring formula
├── index.py         # InvertedIndex data structure
├── tokenizer.py     # Text preprocessing + stemmer
├── models.py        # Pydantic models
├── auth.py          # API key auth
├── .env.example
├── requirements.txt
├── EXPLANATION.md
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| Inverted index | `index.py` — term → {doc_id: freq} |
| TF-IDF + BM25 | `bm25.py` — IDF formula + BM25 scoring |
| Term frequency saturation | `bm25.py` — k1 parameter |
| Length normalization | `bm25.py` — b parameter, avgdl |
| Porter stemmer | `tokenizer.py` — suffix stripping |
| JSON persistence | `index.py` — save/load with int↔str key conversion |
| Facade pattern | `engine.py` — single entry point over 3 components |
| Auto-save on shutdown | `main.py` — lifespan context manager |

## What's next

Project 13 (Basic RAG Pipeline) combines this BM25 engine with the Vector Store from Project 8 and the Embedding Service from Project 7 into a complete retrieval system. Project 14 adds hybrid search — merging BM25 and vector results with Reciprocal Rank Fusion.
