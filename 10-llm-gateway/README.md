# LLM Gateway

A unified FastAPI gateway for LLM providers. Wraps Anthropic's Claude API (and a mock for testing) with retry logic, streaming via Server-Sent Events, token counting, cost estimation, and per-request usage tracking.

## What it does

- Send messages to an LLM, get a completion back
- Stream responses token-by-token using SSE
- Count tokens before sending (avoid context window overflows)
- Estimate cost for any token count + model combination
- Track every request: tokens used, cost, latency, per-model breakdown

## Why a gateway instead of calling the LLM directly?

In production you never call LLM APIs directly from application code:
- **Observability** — you need to know how many tokens every query consumed
- **Cost control** — track spend per model, per feature, per user
- **Retry logic** — APIs rate-limit and fail; the gateway handles retries
- **Swappability** — swap Anthropic for OpenAI by changing one parameter

## Setup

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/10-llm-gateway

pip install -r requirements.txt
cp .env.example .env
# Set API_KEY and optionally ANTHROPIC_API_KEY

uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for the Swagger UI.

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Health check + usage summary |
| POST | `/complete` | ✅ | Single LLM completion |
| POST | `/complete/stream` | ✅ | Streaming completion (SSE) |
| POST | `/tokens/count` | ✅ | Count tokens in text |
| POST | `/tokens/cost` | ✅ | Estimate cost for token counts |
| GET | `/usage` | ✅ | Full usage summary |
| GET | `/usage/recent` | ✅ | Recent request log |
| DELETE | `/usage` | ✅ | Clear usage log |

---

## Usage

### Single completion

```bash
curl -X POST http://localhost:8000/complete \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is RAG?"}],
    "provider": "mock",
    "system": "Be concise.",
    "max_tokens": 256
  }'
```

**Response:**
```json
{
  "content": "Mock response to: What is RAG?",
  "model": "mock-llm-v1",
  "provider": "mock",
  "input_tokens": 12,
  "output_tokens": 8,
  "total_tokens": 20,
  "latency_ms": 52.3,
  "cost": {"total_cost": 0.0, "currency": "USD"},
  "request_id": 1
}
```

### Streaming (SSE)

```bash
curl -X POST http://localhost:8000/complete/stream \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Tell me about RAG"}], "provider": "mock"}'
```

**Response stream:**
```
data: {"token": "Mock "}
data: {"token": "response "}
data: {"token": "to: "}
data: [DONE]
```

### Token counting

```bash
curl -X POST http://localhost:8000/tokens/count \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Retrieval-Augmented Generation combines search with generation."}'
```

### Cost estimation

```bash
curl -X POST http://localhost:8000/tokens/cost \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"input_tokens": 1000, "output_tokens": 500, "model": "claude-3-5-haiku-20241022"}'
```

---

## Providers

| Provider | Models | Requires |
|---|---|---|
| `mock` | mock-llm-v1 | Nothing — works out of the box |
| `anthropic` | claude-3-5-haiku, claude-sonnet-4, claude-3-opus | `ANTHROPIC_API_KEY` + `pip install anthropic` |

---

## Project Structure

```
10-llm-gateway/
├── main.py        # FastAPI routes
├── providers.py   # AnthropicProvider + MockProvider + retry logic
├── tokens.py      # Token counting + cost estimation
├── tracker.py     # Request logging + usage summary
├── models.py      # Pydantic models
├── auth.py        # API key auth
├── .env.example
├── requirements.txt
├── EXPLANATION.md
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| Abstract base class | `BaseProvider` in `providers.py` |
| Async/await | All provider methods |
| Exponential backoff with jitter | `retry_with_backoff()` |
| Server-Sent Events (SSE) | `POST /complete/stream` |
| `StreamingResponse` | `main.py` — FastAPI streaming |
| `AsyncGenerator` | `stream()` method in providers |
| Thread-safe tracking | `RequestTracker` with `threading.Lock` |
| Token counting | `tokens.py` — exact + approximate |
| Cost per model | `TOKEN_COSTS` dict in `tokens.py` |

## What's next

Project 11 (Prompt Engineering Toolkit) builds a library of reusable prompt templates using Jinja2. Project 13 (Basic RAG Pipeline) uses this gateway as the generation step — retrieving chunks then sending them to the LLM via this service.
