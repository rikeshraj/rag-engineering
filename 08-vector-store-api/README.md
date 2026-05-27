# Vector Store API

A REST API that stores vector embeddings in PostgreSQL using the `pgvector` extension and provides fast cosine similarity search. Supports collection namespacing, metadata filtering, and batch operations.

## What it does

- Store document chunks with their embeddings
- Search for the k most similar documents to a query embedding
- Filter search by collection and source
- Batch insert hundreds of documents in one request
- Namespace documents into collections (like folders)
- Full CRUD on documents and collections

## How similarity search works

```
Query text → Embedding Service → query_vector
                                      ↓
              Vector Store: ORDER BY embedding <=> query_vector LIMIT k
                                      ↓
                         Top-k most similar documents
```

pgvector's `<=>` operator computes cosine distance. The HNSW index makes this fast even with millions of documents — it searches a graph of nearest neighbours rather than scanning every row.

## Setup

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/08-vector-store-api

cp .env.example .env
# Set API_KEY, POSTGRES_PASSWORD in .env

# Start PostgreSQL with pgvector + API
make up

# Check it's running
make health
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Health check + document count |
| POST | `/documents` | ✅ | Insert one document |
| POST | `/documents/batch` | ✅ | Insert many documents |
| GET | `/documents/{id}` | ✅ | Get document by ID |
| DELETE | `/documents/{id}` | ✅ | Delete document by ID |
| POST | `/search` | ✅ | Similarity search |
| GET | `/collections` | ✅ | List all collections |
| DELETE | `/collections/{name}` | ✅ | Delete all docs in collection |
| GET | `/stats` | ✅ | Total docs + collection breakdown |

---

## Usage

### Insert a document

```bash
curl -X POST http://localhost:8000/documents \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "RAG combines retrieval with generation.",
    "embedding": [0.1, -0.2, ...],
    "source": "rag_intro.pdf",
    "collection": "rag_docs",
    "metadata": {"page": 1, "chunk_index": 0}
  }'
```

### Batch insert (faster for many documents)

```bash
curl -X POST http://localhost:8000/documents/batch \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"content": "chunk 1", "embedding": [...], "collection": "docs"},
      {"content": "chunk 2", "embedding": [...], "collection": "docs"}
    ]
  }'
```

### Search

```bash
curl -X POST http://localhost:8000/search \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "embedding": [0.1, -0.2, ...],
    "k": 5,
    "collection": "rag_docs",
    "min_score": 0.5
  }'
```

**Response:**
```json
{
  "query_k": 5,
  "returned": 3,
  "collection_filter": "rag_docs",
  "results": [
    {
      "id": 1,
      "content": "RAG combines retrieval with generation.",
      "score": 0.923,
      "source": "rag_intro.pdf",
      "metadata": {"page": 1}
    }
  ]
}
```

---

## Project Structure

```
08-vector-store-api/
├── main.py            # FastAPI routes
├── store.py           # All DB operations (insert, search, delete)
├── database.py        # pgvector schema + connection
├── models.py          # Pydantic request/response models
├── auth.py            # API key auth
├── Dockerfile         # Multi-stage build
├── docker-compose.yml # API + pgvector PostgreSQL
├── Makefile           # Shortcut commands
├── .env.example
├── requirements.txt
├── EXPLANATION.md
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| pgvector extension | `database.py` — `CREATE EXTENSION IF NOT EXISTS vector` |
| HNSW index | `database.py` — `USING hnsw (embedding vector_cosine_ops)` |
| Cosine distance `<=>` | `store.py` — `ORDER BY embedding <=> query_vec` |
| Similarity from distance | `store.py` — `1 - (embedding <=> query_vec)` |
| Metadata filtering | `store.py` — WHERE before ORDER BY |
| Batch insert | `store.py` — single transaction for all rows |
| `pgvector/pgvector:pg15` image | `docker-compose.yml` — pgvector pre-installed |

## HNSW vs IVFFlat

pgvector supports two index types:

| | HNSW | IVFFlat |
|---|---|---|
| Build time | Slower | Faster |
| Query time | Faster | Slower |
| Memory | More | Less |
| Best for | Production queries | Large datasets, batch indexing |

HNSW is the better default for a query-heavy API.

## What's next

Project 9 (BM25 Search Engine) adds keyword search alongside this vector search. Project 13 combines both into a hybrid RAG pipeline.
