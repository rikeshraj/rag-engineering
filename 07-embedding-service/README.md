# Embedding Service

A FastAPI service that converts text into vector embeddings. Supports OpenAI's `text-embedding-3-small` and a mock provider for development and testing. Includes in-memory caching, async batch processing, and cosine similarity computation.

## What it does

- Embed a single text → returns a vector of floats
- Embed a batch of texts concurrently → returns all vectors
- Compute cosine similarity between two texts
- Cache repeated requests — same text never hits the API twice
- Monitor cache hit rate and size

## Setup

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/07-embedding-service

pip install -r requirements.txt

cp .env.example .env
# Set API_KEY in .env
# Set OPENAI_API_KEY if using provider=openai

uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Health check + available providers |
| POST | `/embed` | ✅ | Embed a single text |
| POST | `/embed/batch` | ✅ | Embed multiple texts concurrently |
| POST | `/similarity` | ✅ | Cosine similarity between two texts |
| GET | `/cache/stats` | ✅ | Cache hit rate and size |
| DELETE | `/cache` | ✅ | Clear the cache |

---

## Usage

### Embed a single text

```bash
curl -X POST http://localhost:8000/embed \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "What is retrieval-augmented generation?", "provider": "mock"}'
```

**Response:**
```json
{
  "provider": "mock",
  "model": "mock-embedding-v1",
  "dimensions": 1536,
  "token_count": 5,
  "latency_ms": 1.2,
  "cached": false,
  "embedding": [0.023, -0.041, ...]
}
```

### Embed a batch

```bash
curl -X POST http://localhost:8000/embed/batch \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["What is RAG?", "How do embeddings work?", "What is cosine similarity?"],
    "provider": "mock",
    "concurrency": 5
  }'
```

### Compute similarity

```bash
curl -X POST http://localhost:8000/similarity \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text_a": "How does RAG work?",
    "text_b": "Explain retrieval-augmented generation",
    "provider": "mock"
  }'
```

**Response:**
```json
{
  "cosine_similarity": 0.823,
  "interpretation": "High similarity — closely related topics"
}
```

---

## Providers

| Provider | Model | Dimensions | Requires |
|---|---|---|---|
| `mock` | mock-embedding-v1 | 1536 | Nothing — works out of the box |
| `openai` | text-embedding-3-small | 1536 | `OPENAI_API_KEY` + `pip install openai` |

Use `mock` for development and testing. Switch to `openai` for production.

---

## Project Structure

```
07-embedding-service/
├── main.py          # FastAPI app + all routes
├── embedder.py      # Providers, cache, base class
├── models.py        # Pydantic request/response models
├── auth.py          # API key authentication
├── .env.example     # Environment variable template
├── requirements.txt
├── EXPLANATION.md
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| Abstract base class | `BaseEmbeddingProvider` — shared interface |
| Async/await | `embed()`, `embed_batch()`, `_embed_single()` |
| `asyncio.gather` | Concurrent batch embedding |
| `asyncio.Semaphore` | Rate limiting concurrent API calls |
| SHA-256 hashing | Cache key generation |
| LRU-style eviction | `EmbeddingCache` — evict oldest on overflow |
| Cosine similarity | `cosine_similarity()` in `main.py` |
| Lazy initialization | OpenAI client + tiktoken encoder |
| Factory pattern | `get_provider()` — provider selection by name |

## Cosine Similarity Reference

| Score | Meaning |
|---|---|
| ≥ 0.90 | Very high — near-identical meaning |
| 0.75–0.90 | High — closely related |
| 0.50–0.75 | Moderate — some shared concepts |
| 0.25–0.50 | Low — loosely related |
| < 0.25 | Very low — unrelated |

## What's next

Project 8 (Vector Store API) stores these embeddings in PostgreSQL using `pgvector` and provides similarity search — finding the k most similar chunks to a query embedding.
