# Embedding Service — File-by-File Breakdown

A complete explanation of every file in the project, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
07-embedding-service/
├── main.py          # FastAPI app + routes
├── embedder.py      # Providers, cache, base class
├── models.py        # Pydantic request/response models
├── auth.py          # API key auth (same pattern as Project 4)
├── .env.example
├── requirements.txt
├── README.md
├── EXPLANATION.md
└── tests/
    └── test_embedder.py
```

### How the files connect

```
main.py
  ├── embedder.py  ← providers + cache
  ├── models.py   ← request/response shapes
  └── auth.py     ← API key verification
```

---

## `embedder.py`

### What it does
The core library. Contains the cache, the abstract base provider, two concrete providers (OpenAI and Mock), and a factory function. This file can be used completely independently of FastAPI — as a standalone library.

---

### `EmbeddingResult` and `BatchEmbeddingResult` dataclasses

```python
@dataclass
class EmbeddingResult:
    text: str
    embedding: list[float]
    provider: str
    model: str
    dimensions: int
    token_count: int = 0
    latency_ms: float = 0.0
    cached: bool = False
```

**Why track `latency_ms` and `cached`?**
In a production RAG system, embedding latency is a significant part of total query time. Tracking it per result lets you build dashboards showing where time is spent. The `cached` flag tells you the actual API call rate — critical for understanding costs.

**Why `text_preview` in `to_dict()`?**
The full text is not returned in the API response — only the first 100 characters. Returning the full text would double the response size for long documents and expose input data unnecessarily. The embedding vector is what the caller needs; the text was already sent in the request.

---

### `EmbeddingCache`

```python
class EmbeddingCache:
    def _make_key(self, provider: str, model: str, text: str) -> str:
        raw = f"{provider}:{model}:{text}"
        return hashlib.sha256(raw.encode()).hexdigest()
```

**Why hash the key?**
Dictionary keys in Python can be any hashable type, including long strings. But using the full text as a key means storing it twice — once as a key, once potentially in the value. SHA-256 collapses any text length to a fixed 64-character hex string. The collision probability is astronomically low (~1 in 10^77).

**Why include `provider` and `model` in the key?**
The same text embedded by different models produces different vectors. `"hello world"` via `text-embedding-3-small` returns 1536 floats. Via a different model it returns different floats. Including the model in the key prevents cache poisoning — returning the wrong model's embedding.

**LRU-style eviction:**
```python
if len(self._store) >= self._max_size:
    oldest = next(iter(self._store))
    del self._store[oldest]
```
Python dicts preserve insertion order since 3.7. The first key is the oldest. This is O(1) eviction — no need for a `collections.OrderedDict` or a proper LRU implementation. For a cache this size (max 2000 entries), simple FIFO eviction is indistinguishable from LRU in practice.

**`hit_rate` property:**
```python
@property
def hit_rate(self) -> float:
    total = self.hits + self.misses
    return round(self.hits / total, 4) if total > 0 else 0.0
```
Guards against division by zero on the first call. A cache that's never been queried has a hit rate of 0.0, not an error.

---

### `BaseEmbeddingProvider`

```python
class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def _embed_single(self, text: str) -> tuple[list[float], int]:
        ...

    async def embed(self, text: str) -> EmbeddingResult:
        # check cache → call _embed_single → store in cache → return
```

**The template method pattern:**
Subclasses implement `_embed_single()` — the provider-specific API call. The base class handles caching, timing, and error-checking in `embed()`. This means every provider gets caching for free without duplicating that logic.

**Why `_embed_single` returns a tuple `(embedding, token_count)`?**
Different providers report token usage differently. OpenAI returns it in the API response. The mock provider estimates it from word count. Returning both together keeps the interface clean — the caller doesn't need to know how token counting works for each provider.

**`embed_batch()` with semaphore:**
```python
semaphore = asyncio.Semaphore(concurrency)

async def embed_with_limit(text: str) -> EmbeddingResult:
    async with semaphore:
        return await self.embed(text)

results = await asyncio.gather(*[embed_with_limit(t) for t in texts])
```

`asyncio.gather` launches all coroutines concurrently. Without the semaphore, 100 texts would fire 100 simultaneous API calls — likely triggering rate limiting. The semaphore allows at most `concurrency` (default: 5) calls to be in-flight at once.

Note that cached results don't count toward the semaphore — `self.embed()` returns from cache before ever acquiring it. This means a batch of 100 texts where 80 are cached only runs 20 real API calls.

**Why `asyncio.gather` instead of a loop?**
A loop would embed texts sequentially — 100 texts at 50ms each = 5 seconds. `asyncio.gather` runs them concurrently — 100 texts at 50ms with concurrency=5 = ~1 second (20 batches of 5 × 50ms). The speedup is proportional to concurrency.

---

### `OpenAIEmbeddingProvider`

```python
self._client = None  # lazy init

def _get_client(self):
    if self._client is None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self._api_key)
    return self._client
```

**Why lazy initialization?**
The OpenAI client does network setup on creation. If you import `OpenAIEmbeddingProvider` but use `MockEmbeddingProvider`, you shouldn't pay that cost. Lazy init defers it until `.embed()` is actually called.

**Why `AsyncOpenAI` instead of `OpenAI`?**
The service is async (FastAPI routes are async). Using the sync client inside an async route would block the event loop — no other requests could be handled while waiting for the OpenAI response. `AsyncOpenAI` uses `httpx` under the hood and properly awaits responses.

**`text-embedding-3-small` model:**
At ~$0.02 per 1M tokens, this is OpenAI's cheapest embedding model and has excellent quality for RAG. A typical document chunk of 512 characters ≈ 128 tokens ≈ $0.0000026. You'd need to embed 400,000 chunks to spend $1.

---

### `MockEmbeddingProvider`

```python
async def _embed_single(self, text: str) -> tuple[list[float], int]:
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    raw = []
    for i in range(self._dimensions):
        seed = (seed * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
        raw.append((seed / (2 ** 64)) * 2 - 1)

    # L2 normalize
    magnitude = math.sqrt(sum(x * x for x in raw))
    embedding = [x / magnitude for x in raw]
    await asyncio.sleep(0.001)
    return embedding, len(text.split())
```

**Why use a linear congruential generator (LCG)?**
The goal is a deterministic PRNG that produces different sequences from different seeds. LCG is the simplest: `next = (a * current + c) % m`. The constants used (`6364136223846793005`, `1442695040888963407`) are from Knuth's MMIX — well-studied values that produce good statistical randomness.

**Why L2 normalize?**
Real embedding models return unit vectors — their magnitude is 1.0. This is required for cosine similarity to work correctly (without normalization, longer texts would dominate similarity scores just because of magnitude). L2 normalization divides each component by the vector's Euclidean length, placing the vector on the unit sphere.

**Why `await asyncio.sleep(0.001)`?**
Simulates network latency. Without any await, the mock function completes instantly — making it hard to test latency tracking and async behavior. A 1ms sleep makes it behave more like a real API call without slowing tests meaningfully.

**Important limitation:** Mock embeddings are not semantically meaningful. "cat" and "kitten" will not have high similarity in the mock — their vectors are random relative to each other. The mock is only useful for testing the pipeline infrastructure, not retrieval quality.

---

### The factory function

```python
PROVIDERS = {
    "openai": OpenAIEmbeddingProvider,
    "mock":   MockEmbeddingProvider,
}

def get_provider(provider, cache=None, **kwargs):
    return PROVIDERS[provider](cache=cache, **kwargs)
```

`**kwargs` is passed through so provider-specific arguments work:
```python
# dimensions only applies to MockEmbeddingProvider
get_provider("mock", dimensions=384)

# api_key only applies to OpenAIEmbeddingProvider
get_provider("openai", api_key="sk-...")
```

---

## `main.py`

### What it does
The FastAPI application. Six routes: health, embed single, embed batch, similarity, cache stats, clear cache.

### Key decisions

**Shared `cache` instance:**
```python
cache = EmbeddingCache(max_size=2000)
```
One cache instance is created at module level and shared across all requests. This is correct for an in-process cache — all requests to the same worker process share it. In a multi-worker deployment (`--workers 4`), each worker has its own cache — no sharing across workers. For cross-worker caching, Redis would be used.

**`cosine_similarity()` in `main.py` instead of `embedder.py`:**
Cosine similarity is a math operation on vectors — it doesn't depend on any embedding provider. Putting it in `main.py` keeps `embedder.py` focused on producing embeddings. Math utilities belong with the code that uses them.

```python
def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return round(dot / (mag_a * mag_b), 6)
```

For unit vectors (which all providers return), this simplifies to `dot(a, b)` — the magnitudes are both 1. The full formula is kept for correctness in case non-normalized vectors are ever passed.

**`DELETE /cache` returns 204 No Content:**
HTTP 204 is the correct status for a successful operation that produces no response body. Using 200 with `{"message": "cleared"}` would work but 204 is more semantically accurate — there's nothing to return.

**`get_provider_or_422()` helper:**
```python
def get_provider_or_422(provider_name: str):
    try:
        return get_provider(provider_name, cache=cache)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
```
Converts a `ValueError` (unknown provider name) into a 422 HTTP response with a clear message. Without this, FastAPI would return a 500 Internal Server Error for an unknown provider — which implies a server bug, not a client mistake.

---

## `models.py`

### Key decisions

**`max_length=100` on `EmbedBatchRequest.texts`:**
Limits batch size to 100 texts per request. Without this, a client could send 10,000 texts and exhaust memory or hit API rate limits. The limit is enforced by Pydantic before any embedding code runs.

**`concurrency: int = Field(ge=1, le=20)`:**
Limits the semaphore value. Setting concurrency=100 on a 10-text batch would be harmless but misleading. Setting it higher than the API's rate limit would cause failures. Capping at 20 keeps behavior predictable.

**Separate `EmbedResponse` and `EmbedBatchResponse`:**
The batch response wraps a list of `EmbedResponse` objects and adds aggregate fields (`total_texts`, `total_tokens`, `cache_hits`). These aggregates are only meaningful for batches — not single embeds.

---

## `tests/test_embedder.py`

### Key decisions

**Testing the mock provider, not OpenAI:**
Tests never call the real OpenAI API — they use `MockEmbeddingProvider`. This means tests run without an API key, in CI/CD, and without cost. The mock's behavior (deterministic, unit-normalized, caching) is itself tested.

**`asyncio.run()` to test async functions:**
pytest doesn't run async test functions by default. `asyncio.run(provider.embed(...))` runs the coroutine synchronously inside the test. An alternative is `pytest-asyncio`, but adding a dependency just for this is unnecessary.

**Testing cache eviction:**
```python
def test_evicts_oldest_when_full(self):
    # fill to max_size=3, then add one more
    self.cache.set("mock", "m", "d", [4.0])
    assert self.cache.get("mock", "m", "a") is None
    assert self.cache.get("mock", "m", "d") == [4.0]
```
This verifies the eviction policy works correctly. Without this test, a bug in eviction would silently grow the cache indefinitely, eventually consuming all available memory.

**Testing the API with `TestClient`:**
The FastAPI `TestClient` runs the full application in-process — middleware, dependency injection, Pydantic validation, and route handlers all execute normally. This is a true integration test, not a unit test of individual functions.

---

## `requirements.txt`

```
fastapi>=0.110.0
uvicorn>=0.27.0
pydantic>=2.0.0
python-dotenv>=1.0.0
openai>=1.0.0       # only needed for provider=openai
pytest>=7.0         # optional
httpx>=0.27.0       # optional, needed by TestClient
```

`openai` is listed as a requirement even though `MockEmbeddingProvider` doesn't need it. This simplifies setup — in production you'll want OpenAI anyway. The mock provider lazy-imports nothing (it's pure Python), so the package being installed doesn't affect the mock's startup cost.
