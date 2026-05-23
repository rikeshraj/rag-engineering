# Document Chunker

A CLI tool and Python library that splits documents into chunks ready for embedding in a RAG pipeline. Supports four chunking strategies and multiple file formats.

## Why chunking matters

Every RAG system starts here. How you split documents directly affects retrieval quality:
- Chunks too small → not enough context for the LLM to answer
- Chunks too large → relevant info diluted, context window exceeded
- Bad boundaries → sentences split mid-way, incoherent chunks

## Strategies

| Strategy | How it works | Best for |
|---|---|---|
| `fixed` | Fixed character window with overlap | Baseline, uniform text |
| `sentence` | Accumulate sentences up to chunk_size | Prose, articles, reports |
| `recursive` | Try `\n\n` → `\n` → `.` → ` ` → chars | General purpose (default) |
| `token` | Split by token count via tiktoken | Precise context window control |

## Setup

```bash
git clone https://github.com/yourname/rag-engineering
cd rag-engineering/06-document-chunker

# No required dependencies for fixed/sentence/recursive strategies
# Optional installs:
pip install pdfplumber    # for PDF support
pip install python-docx   # for DOCX support
pip install tiktoken      # for token-based chunking
```

## Usage

```bash
# Default: recursive strategy, 512 chars, 50 overlap
python main.py sample_document.txt

# Choose strategy
python main.py doc.txt --strategy sentence
python main.py doc.txt --strategy fixed --chunk-size 256 --overlap 30

# Save chunks as JSON
python main.py doc.txt --output chunks.json

# Print each chunk preview
python main.py doc.txt --show-chunks

# Compare all strategies side by side
python main.py doc.txt --compare
```

## Example output

```
============================================================
  CHUNKING SUMMARY
============================================================
  Source       : sample_document.txt
  Strategy     : recursive
  Chunk size   : 512 chars
  Overlap      : 50 chars
  Total chars  : 3,842
  Total chunks : 10
  Avg chunk    : 421.3 chars
============================================================
```

## Compare mode

```bash
python main.py sample_document.txt --compare
```

```
============================================================
  STRATEGY COMPARISON  (chunk_size=512, overlap=50)
============================================================
  Strategy       Chunks   Avg size      Min      Max
  ------------ -------- ---------- -------- --------
  fixed               9      460.0      256      512
  sentence            8      479.8      210      512
  recursive          10      421.3      180      512
```

## Use as a library

```python
from chunker import get_chunker

# Get a chunker
chunker = get_chunker("recursive", chunk_size=512, chunk_overlap=50, source="my_doc.txt")

# Chunk some text
result = chunker.chunk(text)

print(f"Total chunks: {result.total_chunks}")
print(f"Avg size:     {result.avg_chunk_size} chars")

for chunk in result.chunks:
    print(chunk.index, chunk.token_estimate, chunk.text[:80])

# Export to JSON
import json
json.dumps(result.to_dict(), indent=2)
```

## Project Structure

```
06-document-chunker/
├── main.py               # CLI entry point
├── chunker.py            # All chunking strategies + factory
├── sample_document.txt   # RAG intro text for testing
├── requirements.txt
└── README.md
```

## Key Concepts Used

| Concept | Where |
|---|---|
| Abstract base class | `BaseChunker` — shared interface for all strategies |
| Dataclasses | `Chunk`, `ChunkResult` |
| Factory pattern | `get_chunker()` — strategy selection by name |
| Recursive algorithm | `RecursiveChunker._split_recursive()` |
| Regex sentence splitting | `SentenceChunker.SENTENCE_END` |
| Lazy import | tiktoken imported only when `TokenChunker` is used |
| `@property` | `Chunk.token_estimate`, `ChunkResult.total_chunks` |

## Running Tests (Optional)

```bash
pip install pytest
pytest tests/ -v
```

## What's next

Project 7 (Embedding Service) takes the chunks produced here and converts each one into a vector embedding using OpenAI or HuggingFace — the next step in the RAG pipeline.
