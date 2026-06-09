# LLM Gateway — File-by-File Breakdown

A complete explanation of every file, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
10-llm-gateway/
├── main.py        # FastAPI routes
├── providers.py   # LLM providers + retry logic
├── tokens.py      # Token counting + cost estimation
├── tracker.py     # Request logging + usage summary
├── models.py      # Pydantic models
└── auth.py        # API key auth
```

### How the files connect

```
main.py
  ├── providers.py  ← LLM API calls, streaming, retry
  │     └── tokens.py  ← cost estimation per result
  ├── tokens.py     ← token counting endpoints
  ├── tracker.py    ← log every request
  └── models.py     ← request/response shapes
```

---

## `tokens.py`

### What it does
Two responsibilities: count tokens before sending to an LLM, and estimate cost for a given token count + model.

### Why token counting matters

Every LLM has a context window limit. Claude's is 200,000 tokens. Sending more than that causes an API error. Token counting before the call lets you reject oversized requests at the gateway level — before spending network time on a request that will fail.

Cost is proportional to tokens. Knowing the count before the call lets you:
- Warn users when a request will be expensive
- Enforce per-user token budgets
- Log actual spend accurately

### Approximate vs exact counting

```python
def count_tokens_approx(text: str) -> int:
    return max(1, len(text) // 4)   # ~4 chars per token for English

def count_tokens_exact(text: str, model: str = "cl100k_base") -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except ImportError:
        return count_tokens_approx(text)
```

**Why two approaches?**
Tiktoken is OpenAI's tokenizer — exact for GPT models, close for Claude. But it adds a dependency. The approximation (÷4) overestimates slightly — safer than underestimating. The exact counter falls back to approximate if tiktoken isn't installed, so the gateway works with zero dependencies.

**Why always overestimate?**
Underestimating is dangerous — you might accept a request you think is 95k tokens but is actually 105k, causing the API call to fail. Overestimating wastes a small margin but never causes failures.

### Cost table

```python
TOKEN_COSTS = {
    "claude-3-5-haiku-20241022": (0.80, 4.00),   # (input, output) per 1M tokens
    "claude-sonnet-4-20250514":  (3.00, 15.00),
    ...
}

def estimate_cost(input_tokens, output_tokens, model):
    input_price, output_price = TOKEN_COSTS[model]
    input_cost  = (input_tokens  / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return {"total_cost": round(input_cost + output_cost, 6), ...}
```

**Why separate input and output prices?**
Every LLM API charges more for output tokens than input tokens — generating text is more computationally expensive than reading it. Claude Haiku charges $0.80/M input but $4.00/M output — 5× more. Tracking both separately gives an accurate cost breakdown.

---

## `providers.py`

### What it does
LLM provider implementations with a shared interface, retry logic, and streaming support.

### `CompletionResult` dataclass

```python
@dataclass
class CompletionResult:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: dict
    cached: bool = False
    stop_reason: str = "end_turn"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
```

Every completion returns a `CompletionResult` regardless of provider. The tracker, the API response, and any downstream code all work with this one type — the provider identity is contained in the `provider` field.

### `retry_with_backoff()`

```python
async def retry_with_backoff(coro_fn, max_retries=3, base_delay=1.0, ...):
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except retryable_errors as e:
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * 0.2 * (random.random() * 2 - 1)
            await asyncio.sleep(delay + jitter)
    raise last_error
```

**Exponential backoff:**
Wait 1s after attempt 1, 2s after attempt 2, 4s after attempt 3. The wait doubles each time — rate limits need time to clear, and hammering the API immediately won't help.

**Jitter — why randomness helps:**
Imagine 100 clients all hitting a rate limit at the same time. Without jitter, they all retry at exactly t+1s — hitting the API simultaneously again. With ±20% random jitter, retries spread out over ~0.4s, reducing the pile-on effect. This is called the "thundering herd problem."

**Why pass `coro_fn` (a callable) instead of a coroutine?**
Coroutines are single-use — once awaited, they're done. To retry, you need to create a new coroutine each time. Passing a callable (`lambda: provider._call_api(...)`) lets `retry_with_backoff` call it multiple times.

### `BaseProvider` — template method pattern

```python
class BaseProvider(ABC):
    @abstractmethod
    async def _embed_single(self, ...): ...   # subclass implements this

    async def complete(self, messages, ...):  # base class owns this
        result = await retry_with_backoff(lambda: self._call_api(...))
        result.latency_ms = ...
        result.cost = estimate_cost(...)
        return result
```

Subclasses implement `_call_api()` and `_stream_api()` — the provider-specific parts. The base class handles retry, timing, and cost calculation — shared logic that runs for every provider. Adding a new provider (OpenAI, Gemini) means implementing two methods — everything else is inherited.

### `AnthropicProvider`

```python
async def _call_api(self, messages, model, max_tokens, temperature, system):
    client = self._get_client()
    kwargs = dict(model=model, max_tokens=max_tokens, ...)
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)
    return CompletionResult(
        content=response.content[0].text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        ...
    )
```

**Why `if system: kwargs["system"] = system`?**
Anthropic's API doesn't accept `system=None` — passing it causes a validation error. Conditionally adding it only when it has a value is cleaner than sending `None`.

**Why `response.content[0].text`?**
Anthropic's API can return multiple content blocks (text, tool_use, etc.). For text completions, the first block is always the text. In Project 16 (Agentic RAG), you'll handle `tool_use` blocks too.

### Streaming with `AsyncGenerator`

```python
async def _stream_api(self, messages, model, ...) -> AsyncGenerator[str, None]:
    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text
```

`AsyncGenerator[str, None]` is a type hint meaning: an async generator that yields `str` values and returns `None` when done. The `yield` inside an `async def` makes it a generator — it pauses at each `yield` and resumes when the caller asks for the next value.

**Why `async with` for streaming?**
The `client.messages.stream()` context manager keeps the HTTP connection open for the duration of streaming. `async with` ensures the connection is properly closed even if the consumer stops reading mid-stream.

### `MockProvider` — deterministic responses

```python
async def _call_api(self, messages, model, max_tokens, ...):
    await asyncio.sleep(0.05)   # simulate latency
    last_msg = messages[-1].get("content", "")[:50]
    content = f"Mock response to: {last_msg}"
    ...
```

The mock always produces the same response for the same input — deterministic. This is essential for test assertions: you know exactly what to expect. The 50ms sleep simulates network latency so latency-tracking tests behave realistically.

---

## `tracker.py`

### What it does
Thread-safe in-memory request log with running totals and per-model breakdown.

### Thread safety with `Lock`

```python
from threading import Lock

class RequestTracker:
    def __init__(self):
        self._lock = Lock()

    def log(self, result):
        with self._lock:
            # all mutations happen inside the lock
            self._records.append(record)
            self._total_requests += 1
            ...
```

**Why thread safety?**
FastAPI runs with multiple workers (uvicorn `--workers 4`). Each worker is a separate OS thread. Without locking, two threads could simultaneously increment `_total_requests` — both read 5, both write 6, when the correct answer is 7. This is a race condition. The `Lock` ensures only one thread modifies state at a time.

**Why `threading.Lock` instead of `asyncio.Lock`?**
FastAPI route handlers are async — they run on the event loop. But the event loop is single-threaded per worker. With multiple workers, you need OS-level thread synchronization, not asyncio synchronization. `threading.Lock` works across threads; `asyncio.Lock` only works within a single event loop.

### Running totals pattern

```python
self._total_requests = 0
self._total_input_tokens = 0

def log(self, result):
    with self._lock:
        self._total_requests += 1
        self._total_input_tokens += result.input_tokens
```

Rather than summing all records on every `summary()` call (O(n)), running totals are maintained incrementally — O(1) update on log, O(1) read on summary. At 1000 requests/second, O(n) summary would be noticeably slow.

### `defaultdict` for per-model breakdown

```python
from collections import defaultdict

self._by_model: dict[str, dict] = defaultdict(lambda: {
    "requests": 0, "input_tokens": 0, "output_tokens": 0, "total_cost": 0.0
})
```

`defaultdict(factory)` creates the default value automatically on first access. Without it, you'd need to check `if model not in self._by_model` before every update. The lambda returns a fresh dict for each new model key.

### Max records cap

```python
self._records.append(record)
if len(self._records) > self._max_records:
    self._records.pop(0)
```

The list is capped at `max_records` (default 1000) to prevent unbounded memory growth. When full, the oldest record is removed. `pop(0)` is O(n) on a list — a `collections.deque(maxlen=1000)` would be O(1), but for 1000 records the difference is negligible.

---

## `main.py`

### What it does
Eight routes: health, complete, stream, token count, cost estimate, usage summary, recent log, clear usage.

### Streaming with `StreamingResponse`

```python
async def event_generator():
    async for token in provider.stream(messages=messages, ...):
        event = json.dumps({"token": token})
        yield f"data: {event}\n\n"
    yield "data: [DONE]\n\n"

return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```

**SSE format:**
Every event is `data: {json}\n\n`. The double newline signals end-of-event to the client. The client reads these incrementally — each `data:` line triggers a callback. `[DONE]` is the conventional signal that the stream is complete (same as OpenAI's streaming protocol).

**`X-Accel-Buffering: no`:**
Nginx (a common reverse proxy) buffers responses by default — it waits to collect a full response before forwarding to the client. This breaks streaming. This header tells nginx to forward each chunk immediately as it arrives.

**`Cache-Control: no-cache`:**
Prevents proxies and browsers from caching the SSE stream. Each request should get a fresh stream.

### Why `request_id` in the response

```python
record = tracker.log(result)
return CompleteResponse(**result.to_dict(), request_id=record.request_id)
```

The `request_id` lets callers correlate their API call with the entry in `GET /usage/recent`. If something goes wrong, you can look up the exact request in the log. This is the foundation of distributed tracing.

### Error handling pattern

```python
try:
    result = await provider.complete(messages=messages, ...)
except Exception as e:
    tracker.log_error(body.provider, body.model or "unknown", str(e))
    raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")
```

502 Bad Gateway is the correct status when an upstream service (the LLM API) fails. 500 Internal Server Error implies the bug is in our code. Errors are logged to the tracker even when they fail — total error count is part of the usage summary.

---

## `models.py`

### Key decisions

**`Message.role` validated with regex:**
```python
role: str = Field(pattern="^(user|assistant)$")
```
Only `"user"` and `"assistant"` are valid roles. `"system"` is handled separately via the `system` parameter to avoid confusion. FastAPI returns 422 if any other value is passed — no manual validation needed.

**`temperature: float = Field(ge=0.0, le=1.0)`:**
Temperature outside [0, 1] produces unpredictable behavior. The constraint enforces valid values before they reach the API. Some APIs accept up to 2.0 — the constraint can be relaxed per provider in a production system.

**`max_tokens: int = Field(ge=1, le=8192)`:**
8192 is a reasonable cap for a gateway — prevents accidentally requesting very long responses. Claude's actual limit is higher (8192 for output by default), but the gateway enforces a conservative limit. Adjust per use case.

---

## `tests/test_gateway.py`

### Key test: `test_stream_yields_tokens`

```python
async def collect():
    tokens = []
    async for token in MockProvider().stream([{"role": "user", "content": "Hello"}]):
        tokens.append(token)
    return tokens

tokens = asyncio.run(collect())
assert len(tokens) > 0
```

Tests the async generator directly. The `asyncio.run()` pattern runs the coroutine synchronously inside the test — no need for `pytest-asyncio`. Each yielded value is a word with a trailing space — joining them reconstructs the full response.

### Key test: `test_max_records_cap`

```python
t = RequestTracker(max_records=3)
for _ in range(5):
    t.log(self._make_result())
assert len(t.recent(100)) == 3
```

Verifies the eviction policy — after 5 inserts into a cap-3 tracker, only 3 records remain. Without this test, a bug in eviction would silently grow memory unboundedly.

### Key test: `test_completion_tracked`

```python
client.post("/complete", json={...}, headers=HEADERS)
r = client.get("/usage", headers=HEADERS)
assert r.json()["total_requests"] == 1
```

Verifies the full integration: completing a request causes the tracker to record it, and the usage endpoint reflects the new count. This tests the wiring between `main.py`, `providers.py`, and `tracker.py` together.
