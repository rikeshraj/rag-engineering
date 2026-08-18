# Prompt Engineering Toolkit — File-by-File Breakdown

A complete explanation of every file, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
11-prompt-toolkit/
├── main.py       # FastAPI routes
├── library.py    # 10 pre-built templates + registry
├── templates.py  # PromptTemplate + RenderedPrompt
├── chains.py     # Sequential prompt chaining
├── models.py     # Pydantic models
└── auth.py       # API key auth
```

### How the files connect

```
main.py
  ├── library.py    ← template registry + 10 built-in templates
  │     └── templates.py  ← PromptTemplate class + Jinja2 rendering
  └── chains.py     ← ChainStep + PromptChain + pre-built chains
```

---

## `templates.py`

### What it does
The core template engine. `PromptTemplate` stores a Jinja2 template string with metadata. `RenderedPrompt` is the output — a messages list ready to send to an LLM.

### Why Jinja2 instead of f-strings

```python
# f-string — works for simple cases
prompt = f"Answer this: {question}\n\nContext: {context}"

# Jinja2 — handles conditionals, loops, filters
template = """
{% if examples %}
Examples:
{% for ex in examples %}
Q: {{ ex.question }}
A: {{ ex.answer }}
{% endfor %}
{% endif %}
Question: {{ question }}
"""
```

f-strings require Python code to add conditionals or loops. Jinja2 keeps all prompt logic inside the template string — editable without touching Python. This matters when non-engineers need to tune prompts.

### `StrictUndefined` — fail early, not silently

```python
from jinja2 import Environment, StrictUndefined
env = Environment(undefined=StrictUndefined)
```

Without `StrictUndefined`, a missing variable renders as an empty string:
```
"Answer: {{ missing_var }}" → "Answer: "
```
With `StrictUndefined`, it raises immediately:
```
UndefinedError: 'missing_var' is undefined
```
Silently empty prompts are a subtle, hard-to-debug failure mode. Strict mode surfaces the problem at render time, not at evaluation time when you're wondering why the LLM gave a bad answer.

### Default variable handling — the sentinel pattern

```python
_MISSING = object()
variables = {}
for var in self.variables:
    default = var.default if var.default is not None else (
        None if not var.required else _MISSING
    )
    if default is not _MISSING:
        variables[var.name] = var.default
```

**Why a sentinel instead of checking `is not None`?**
Optional variables can have `default=None` (e.g. `context` in `QUERY_REWRITE`). The template uses `{% if context %}` to conditionally include it. If we skip `None` defaults, Jinja2 raises `UndefinedError` when evaluating `{% if context %}` — the variable doesn't exist at all.

The `_MISSING` sentinel distinguishes "this variable has no default" (required) from "this variable has a default of None" (optional, should be included as `None`).

### Built-in examples fallback

```python
if self.examples and not variables.get("examples"):
    variables["examples"] = self.examples
```

When a template has built-in few-shot examples and the caller doesn't provide custom ones, the built-in examples are used. `not variables.get("examples")` catches both "not provided" and "provided as empty list" — using the built-ins as the sensible default in both cases.

### `RenderedPrompt.user_content()`

```python
def user_content(self) -> str:
    for msg in reversed(self.messages):
        if msg["role"] == "user":
            return msg["content"]
    return ""
```

Scans backwards through messages to find the last user turn. This handles multi-turn conversations correctly — the "current prompt" is always the last user message, not necessarily `messages[0]`.

---

## `library.py`

### What it does
10 pre-built templates organized into a registry dict. Each template demonstrates a different prompting technique.

### The 10 templates and their techniques

**`rag_qa` — standard**
The baseline RAG template. One context block, one question. System prompt explicitly forbids making up information. The simplest possible RAG prompt — correct for most use cases.

**`rag_qa_cot` — chain-of-thought**
```
Let's think step by step:
1. What does the context tell us?
2. What is directly stated vs implied?
3. What is the most accurate answer?

Reasoning: [think through the above]
Final Answer:
```
Chain-of-thought forces the model to reason before answering. For complex questions that require inference across multiple context chunks, this improves accuracy significantly. The numbered steps act as scaffolding — the model fills in each one before reaching the conclusion.

**`rag_qa_few_shot` — few-shot**
```jinja2
{% for ex in examples %}
Context: {{ ex.context }}
Question: {{ ex.question }}
Answer: {{ ex.answer }}
{% endfor %}
```
Few-shot examples show the model the exact output format expected — length, style, citation behavior. Without examples, different models produce wildly different formats. With 2-3 examples, output becomes consistent and predictable.

**`extract_json` — extraction**
The system prompt says "output raw JSON only" and the user prompt ends with "Return ONLY the JSON object, no other text." Both reinforce the constraint. This double-reinforcement is necessary because LLMs tend to add preambles ("Here is the JSON:") even when instructed not to.

**`classify` — classification**
Labels are formatted with `{{ labels | join(", ") }}` — Jinja2's join filter. The system prompt says "output ONLY the label." Classification prompts need to be maximally constrained — any extra text breaks downstream label parsing.

**`answer_grading` — evaluation**
The grading template itself outputs JSON with numeric scores. This is the "LLM-as-judge" pattern used in RAGAS and similar evaluation frameworks. The model evaluates another model's output — automated quality assessment without human annotation.

**`hypothetical_doc` — HyDE**
HyDE (Hypothetical Document Embeddings) is a retrieval technique: instead of embedding the query, generate a hypothetical document that would answer it, then embed that. Hypothetical documents are more similar in style to real documents than queries are — improving retrieval recall.

### The registry pattern

```python
TEMPLATE_REGISTRY: dict[str, PromptTemplate] = {
    t.name: t for t in [RAG_QA, RAG_QA_COT, ...]
}

def get_template(name: str) -> PromptTemplate:
    if name not in TEMPLATE_REGISTRY:
        raise ValueError(f"Template '{name}' not found...")
    return TEMPLATE_REGISTRY[name]
```

Dict lookup is O(1). The `get_template` function adds a clear error message with available options — better than the default `KeyError`. Adding a new template is one line in the list — the dict comprehension handles the rest.

---

## `chains.py`

### What it does
Sequential prompt chaining — output of one template feeds into the next. The foundation of multi-step reasoning.

### `ChainStep.input_map` — flexible input sourcing

```python
@dataclass
class ChainStep:
    input_map: dict[str, str | Callable]
```

Each key in `input_map` is a template variable name. Each value is either:
- A string: look up that key in the chain state
- A callable: call it with the current state and use the return value

```python
ChainStep(
    template=QUERY_REWRITE,
    input_map={
        "query":   "question",              # string: state["question"]
        "context": lambda s: s.get("ctx"),  # callable: transform state
    },
)
```

The callable option lets you transform values between steps — uppercase, truncate, reformat — without adding new template variables or modifying the template.

### Chain state — accumulating dict

```python
state: dict = dict(initial_inputs)   # start with caller's inputs

for step in self.steps:
    inputs = step.resolve_inputs(state)
    rendered = step.template.render(**inputs)
    output = await llm_fn(rendered)
    state[step.output_key] = output   # add to state for next step
```

State grows as the chain runs. Step 1's output becomes available as Step 2's input. This design means any step can read any earlier step's output, not just the immediately preceding one.

**Why dict accumulation instead of passing output directly?**
If Step 1 produces `rewritten_query` and Step 2 needs both `rewritten_query` and the original `context`, direct output passing would lose `context`. The accumulating state dict keeps everything available to all subsequent steps.

### `llm_fn` parameter — dependency injection

```python
async def run(self, llm_fn: Callable, **initial_inputs) -> ChainResult:
    ...
    output = await llm_fn(rendered)
```

The chain doesn't know which LLM to use — it accepts any async function that takes a `RenderedPrompt` and returns a string. This makes chains testable with a mock:

```python
async def mock_llm(rendered):
    return f"Mock: {rendered.user_content()[:30]}"

result = await chain.run(llm_fn=mock_llm, question="...", context="...")
```

And usable with any provider in production:

```python
async def real_llm(rendered):
    result = await anthropic_provider.complete(rendered.messages, system=rendered.system)
    return result.content
```

This is dependency injection — the chain depends on an abstraction (a callable), not a concrete provider.

### Pre-built chains

**`rag_with_rewrite`** — Rewrites the query first, then answers. The rewritten query would be used for retrieval (done outside the chain), and the original context is used for answering. In Project 14 (Hybrid Search RAG), this becomes the basis of query expansion.

**`summarize_then_answer`** — Summarizes long context before answering. Useful when retrieved chunks exceed the context window. The summary step compresses N chunks into 3 sentences, then the QA step answers from the summary.

---

## `main.py`

### Key decisions

**`/render` vs `/run`**
`/render` renders the template and returns the messages without calling any LLM. This is invaluable for debugging — you can inspect the exact prompt that would be sent before spending API tokens. `/run` adds the LLM call on top.

**`call_llm()` — graceful fallback**
```python
try:
    sys.path.insert(0, "../llm-gateway")
    from providers import get_provider
    ...
except (ImportError, ModuleNotFoundError):
    # Built-in mock fallback
    content = f"[Mock] Response to: {last[:80]}"
```
The toolkit tries to import from Project 10's providers for real LLM calls. If that's not available (different working directory, not installed), it falls back to an inline mock. This makes the toolkit usable standalone or integrated.

**Chain `llm_fn` closure**
```python
async def llm_fn(rendered):
    text, _ = await call_llm(
        rendered,
        provider=body.provider,
        model=body.model,
        ...
    )
    return text

result = await chain.run(llm_fn=llm_fn, **body.variables)
```
A closure captures `body.provider`, `body.model`, etc. from the request. The chain only sees a simple callable — it doesn't know about FastAPI or the HTTP layer. Clean separation.

---

## Tests

### Key test: `test_render_missing_variable_422`
```python
r = client.post("/render", json={"template": "rag_qa", "variables": {}})
assert r.status_code == 422
```
`rag_qa` requires `context` and `question`. Sending empty variables should return 422 Unprocessable — FastAPI converts the `ValueError` from `render()` into a 422 response. This tests the full validation pipeline.

### Key test: `test_chain_step_callable_source`
```python
step = ChainStep(
    template=RAG_QA,
    input_map={"question": lambda state: state["q"].upper(), "context": "ctx"},
)
resolved = step.resolve_inputs({"q": "what is rag", "ctx": "..."})
assert resolved["question"] == "WHAT IS RAG"
```
Tests the callable `input_map` path. Verifies that lambda transformations on state values work correctly — important for query preprocessing in chains.

### Key test: `test_chain_run`
Tests the full chain execution with a mock LLM. Verifies: correct number of steps executed, final output is non-empty, intermediate outputs stored in state. Running a 2-step chain with a mock validates all the chain machinery without any LLM dependency.
