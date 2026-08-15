# Prompt Engineering Toolkit

A library of reusable, versioned prompt templates for RAG and LLM tasks. Built with Jinja2 — supports variables, conditionals, loops, and few-shot examples. Includes a FastAPI service and a sequential chain system.

## What it does

- 10 pre-built templates covering standard RAG, chain-of-thought, few-shot, extraction, classification, query rewriting, evaluation, and HyDE
- Render templates with variable substitution and Jinja2 logic
- Send rendered prompts to LLMs and get responses back
- Chain templates sequentially — output of one step feeds the next
- Preview rendered prompts without calling any LLM

## Why Jinja2 for prompts?

f-strings work for simple substitution. Jinja2 adds:
- **Conditionals**: `{% if examples %}...{% endif %}`
- **Loops**: `{% for ex in examples %}...{% endfor %}`
- **Filters**: `{{ labels | join(", ") }}`
- **Strict validation**: `StrictUndefined` catches missing variables at render time

Prompts are code — they deserve the same tooling.

## Setup

```bash
git clone https://github.com/rikeshraj/rag-engineering
cd rag-engineering/11-prompt-toolkit

pip install -r requirements.txt
cp .env.example .env

uvicorn main:app --reload
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Health check |
| GET | `/templates` | ✅ | List all templates |
| GET | `/templates/{name}` | ✅ | Template details |
| POST | `/render` | ✅ | Render without LLM |
| POST | `/run` | ✅ | Render + send to LLM |
| GET | `/chains` | ✅ | List chains |
| POST | `/chains/{name}/run` | ✅ | Run a chain |

---

## Built-in Templates

| Template | Technique | Description |
|---|---|---|
| `rag_qa` | standard | RAG question answering |
| `rag_qa_cot` | chain-of-thought | RAG + step-by-step reasoning |
| `rag_qa_few_shot` | few-shot | RAG + format examples |
| `summarize` | standard | Paragraph summary |
| `summarize_bullets` | standard | Bullet-point summary |
| `extract_json` | extraction | Structured JSON extraction |
| `classify` | classification | Label assignment |
| `query_rewrite` | query-expansion | Better retrieval queries |
| `answer_grading` | evaluation | Faithfulness scoring |
| `hypothetical_doc` | hyde | HyDE retrieval document |

---

## Usage

### Render a template (preview)

```bash
curl -X POST http://localhost:8000/render \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "rag_qa",
    "variables": {
      "context": "RAG stands for Retrieval-Augmented Generation...",
      "question": "What does RAG stand for?"
    }
  }'
```

### Run a template (LLM call)

```bash
curl -X POST http://localhost:8000/run \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "rag_qa_cot",
    "variables": {"context": "...", "question": "..."},
    "provider": "mock"
  }'
```

### Run a chain

```bash
curl -X POST http://localhost:8000/chains/rag_with_rewrite/run \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {"question": "what is rag", "context": "..."},
    "provider": "mock"
  }'
```

---

## Use as a library

```python
from library import get_template, RAG_QA_COT
from chains import CHAIN_REGISTRY

# Render a template
rendered = RAG_QA_COT.render(
    context="RAG combines retrieval with generation.",
    question="What is RAG?",
)
print(rendered.system)
print(rendered.messages[0]["content"])

# Run a chain
chain = CHAIN_REGISTRY["rag_with_rewrite"]
result = await chain.run(
    llm_fn=my_llm_function,
    question="what is rag",
    context="RAG stands for...",
)
print(result.final_output)
```

---

## Project Structure

```
11-prompt-toolkit/
├── main.py        # FastAPI routes
├── library.py     # 10 pre-built templates + registry
├── templates.py   # PromptTemplate + RenderedPrompt classes
├── chains.py      # ChainStep + PromptChain + pre-built chains
├── models.py      # Pydantic models
├── auth.py        # API key auth
├── .env.example
├── requirements.txt
├── README.md
└── EXPLANATION.md
```

