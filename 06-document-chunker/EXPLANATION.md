# Document Chunker — File-by-File Breakdown

A complete explanation of every file in the project, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
06-document-chunker/
├── main.py               # CLI entry point
├── chunker.py            # All chunking strategies + factory
├── sample_document.txt   # RAG intro text for testing
├── requirements.txt
├── README.md
└── tests/
    └── test_chunker.py
```

### How the files connect

```
main.py
  └── chunker.py    ← all strategies, factory, data structures
```

`main.py` handles CLI parsing, file reading, and output formatting. `chunker.py` handles all chunking logic. Neither file knows about the other's concerns — you can use `chunker.py` as a library without ever touching `main.py`.

---

## `chunker.py`

### What it does
The core library. Defines two data structures (`Chunk`, `ChunkResult`), a base class (`BaseChunker`), four chunking strategy classes, and a factory function (`get_chunker`).

---

### `Chunk` dataclass

```python
@dataclass
class Chunk:
    text: str
    index: int
    start_char: int
    end_char: int
    source: str = ""
    metadata: dict = field(default_factory=dict)
```

**Why track `start_char` and `end_char`?**
In a production RAG system, chunks need to be traceable back to their exact position in the source document. If a retrieved chunk is used to answer a question, you need to know where it came from — page number, section, byte offset. `start_char` and `end_char` are the foundation for building that metadata.

**`token_estimate` as a `@property`**
```python
@property
def token_estimate(self) -> int:
    return len(self.text) // 4
```
A rough estimate based on the rule of thumb that 1 token ≈ 4 characters for English text. It's a `@property` rather than a stored value because it's always derivable from `text` — there's no point storing something you can compute. If `text` changes, the estimate updates automatically.

**Why not store `char_count` as a field?**
Same reason — `len(self.text)` is O(1) in Python (string length is stored). Computing it on demand is cheaper than keeping a separate field in sync.

---

### `ChunkResult` dataclass

```python
@dataclass
class ChunkResult:
    chunks: list[Chunk]
    strategy: str
    source: str
    total_chars: int
    chunk_size: int
    chunk_overlap: int
```

**Why a separate result object instead of just returning `list[Chunk]`?**
A plain list loses context — you'd have no way to know what strategy was used, what the chunk size was, or what file it came from. `ChunkResult` bundles the output with the parameters that produced it. This is important for the evaluation phase (Project 15) where you'll compare different chunking configurations against each other.

**`total_chunks` and `avg_chunk_size` as properties**
```python
@property
def total_chunks(self) -> int:
    return len(self.chunks)

@property
def avg_chunk_size(self) -> float:
    return round(sum(len(c.text) for c in self.chunks) / len(self.chunks), 1)
```
Both are derived from `self.chunks`. Properties keep the dataclass as the single source of truth — you can't accidentally have `total_chunks = 5` while `len(chunks) = 6`.

---

### `BaseChunker`

```python
class BaseChunker:
    def __init__(self, chunk_size=512, chunk_overlap=50, source=""):
        if chunk_overlap >= chunk_size:
            raise ValueError(...)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.source = source

    def chunk(self, text: str) -> ChunkResult:
        raise NotImplementedError
```

**Why an abstract base class?**
All four strategies share the same constructor parameters and the same `chunk()` interface. Putting shared behavior in a base class means:
- Adding a new parameter (e.g. `min_chunk_size`) happens once in `BaseChunker`, not in every strategy
- Code that uses a chunker doesn't need to know which strategy it is — it just calls `.chunk(text)`
- The factory function (`get_chunker`) can return any strategy and the caller works the same way

**Why validate `chunk_overlap < chunk_size` in `__init__`?**
Failing fast. If overlap ≥ size, the chunker would either loop forever or produce duplicate chunks. Raising in `__init__` surfaces this as a configuration error immediately, not halfway through chunking a large document.

**`_make_chunks_from_splits()` shared helper**
```python
def _make_chunks_from_splits(self, splits: list[str], text: str) -> list[Chunk]:
```
Both `RecursiveChunker` and `TokenChunker` produce a list of text strings first, then need to build `Chunk` objects with correct character offsets. This helper is shared to avoid duplicating the offset-tracking logic. It uses `text.find(split, cursor)` to locate each split in the original text.

---

### Strategy 1: `FixedSizeChunker`

```python
start = 0
while start < len(text):
    end = min(start + self.chunk_size, len(text))
    splits.append(text[start:end])
    start += self.chunk_size - self.chunk_overlap
```

**The overlap mechanics:**
If `chunk_size=100` and `chunk_overlap=20`, the step forward is `100 - 20 = 80` characters. So:
- Chunk 0: chars 0–100
- Chunk 1: chars 80–180
- Chunk 2: chars 160–260

Chars 80–100 appear in both chunk 0 and chunk 1. This is intentional — if a sentence spans a chunk boundary, at least one chunk contains the complete sentence.

**Why `min(start + chunk_size, len(text))`?**
Prevents the last slice from going past the end of the string. Without it, `text[500:600]` on a 550-character string would silently return a 50-character string — which is fine in Python, but `end_char` would be wrong.

**Limitation:** May split mid-word or mid-sentence. This is acceptable for the fixed strategy — it's a baseline, not a production choice.

---

### Strategy 2: `SentenceChunker`

```python
SENTENCE_END = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$",
    re.MULTILINE
)
```

**How the regex works:**
- `(?<=[.!?])` — lookbehind: character before this position must be `.`, `!`, or `?`
- `\s+` — one or more whitespace characters (the space after the period)
- `(?=[A-Z])` — lookahead: next character must be uppercase (start of new sentence)
- `|(?<=[.!?])\s*$` — or: end of line after punctuation

The lookbehind and lookahead are zero-width — they assert a condition without consuming characters. So splitting on this pattern gives you complete sentences without losing the punctuation.

**Why not use NLTK's sentence tokenizer?**
NLTK's `sent_tokenize` is more accurate but adds a large dependency. The regex handles the vast majority of real-world English text correctly. For a RAG system processing business documents, the edge cases NLTK handles better (abbreviations like "Dr.", "U.S.") rarely change retrieval quality meaningfully.

**Overlap in sentence chunking:**
After flushing a chunk, the code works backwards through `current_sentences` to find sentences that fit within `chunk_overlap` characters:
```python
for s in reversed(current_sentences):
    if overlap_len + len(s) + 1 <= self.chunk_overlap:
        overlap_sentences.insert(0, s)
```
This carries complete sentences as overlap — more semantically meaningful than carrying a fixed number of characters that might start mid-sentence.

---

### Strategy 3: `RecursiveChunker`

```python
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]
```

**The recursive algorithm:**
```
If text fits in chunk_size → return it
Otherwise:
    Try splitting on separators[0]  (paragraph break)
    For each piece:
        If piece fits → keep it
        If piece is still too big → recurse with separators[1:]
```

This guarantees that no chunk ever exceeds `chunk_size`, while always trying to split on the most natural boundary available.

**Why the separator order matters:**
`\n\n` (blank line between paragraphs) is the most semantically meaningful boundary. A chunk that contains a complete paragraph is more coherent than one that cuts mid-paragraph. So we try it first. Only if a single paragraph exceeds `chunk_size` do we fall back to splitting on newlines, then sentences, then words, then characters.

**Why `""` as the last separator?**
An empty string split gives individual characters. It's the absolute last resort — used only if a single word exceeds `chunk_size`. In practice this never happens for normal text, but it makes the algorithm complete — it will always produce chunks within the size limit.

**The `_merge_splits` pass:**
After recursion, many small splits exist. `_merge_splits` combines them back together up to `chunk_size`, with overlap:
```
["The", "quick", "brown", "fox"] + chunk_size=20 →
["The quick brown fox"]
```
Without this pass, you'd get many single-word chunks. The recursive split breaks things apart; the merge pass reassembles them into reasonably sized chunks.

---

### Strategy 4: `TokenChunker`

```python
def _get_encoder(self):
    if self._enc is None:
        import tiktoken
        self._enc = tiktoken.get_encoding(self.model)
    return self._enc
```

**Why lazy initialization (`self._enc = None` then load on first use)?**
The tiktoken encoder takes ~100ms to load. If you create a `TokenChunker` object but don't call `.chunk()`, you shouldn't pay that cost. Lazy initialization defers the load until it's actually needed. It also means the other three strategies work with zero dependencies even in the same file that defines `TokenChunker`.

**Why token-based instead of character-based?**
Character counts are not how LLMs think about text. The word "tokenization" is one token. The word "pneumonoultramicroscopicsilicovolcanoconiosis" is several. A 512-character chunk might be 80 tokens or 200 tokens depending on the vocabulary. When you need to stay within a model's context window, counting tokens is the only accurate approach.

**`cl100k_base` encoding:**
The default encoding used by GPT-4 and compatible with Claude's tokenizer for estimation purposes. OpenAI's `text-embedding-3-small` also uses this encoding. Using the same encoding as your embedding model ensures your chunk sizes accurately reflect what the model will process.

---

### The factory function

```python
STRATEGIES = {
    "fixed":     FixedSizeChunker,
    "sentence":  SentenceChunker,
    "recursive": RecursiveChunker,
    "token":     TokenChunker,
}

def get_chunker(strategy, chunk_size=512, chunk_overlap=50, source=""):
    if strategy not in STRATEGIES:
        raise ValueError(...)
    return STRATEGIES[strategy](chunk_size=chunk_size, ...)
```

**Why a factory instead of direct instantiation?**
The CLI and any external code that uses this library only need to know strategy names as strings — they don't need to import four different classes. Adding a new strategy is one line in the `STRATEGIES` dict. The CLI's `--strategy` choices list is also derived from this dict, so they stay in sync automatically.

---

## `main.py`

### What it does
CLI entry point. Reads a file, runs the chosen chunking strategy, prints a summary, and optionally saves JSON output.

### Key decisions

**`read_file()` supports multiple formats**
The same format-dispatch pattern from Project 1.5 is reused here. PDF and DOCX reading are lazy-imported — no error if the libraries aren't installed unless you actually try to chunk a PDF or DOCX.

**`--compare` mode**
```python
for name in ["fixed", "sentence", "recursive"]:
    chunker = get_chunker(name, chunk_size=chunk_size, ...)
    result = chunker.chunk(text)
    sizes = [len(c.text) for c in result.chunks]
    print(name, result.total_chunks, result.avg_chunk_size, min(sizes), max(sizes))
```
Runs all three stdlib strategies against the same document and prints a comparison table. This is genuinely useful for deciding which strategy to use — you can see at a glance that recursive produces more uniform chunk sizes than fixed, or that sentence produces fewer but larger chunks.

**`print_chunks()` preview**
Shows the first 80 characters of each chunk with its position and token estimate. Makes it easy to visually inspect whether chunks are coherent without opening a JSON file.

**`--output` saves full JSON**
The JSON output from `result.to_dict()` contains every field of every chunk — index, text, start/end offsets, token estimate, source. This is the format that Project 7 (Embedding Service) will consume — each chunk becomes an embedding request.

---

## `tests/test_chunker.py`

### What it does
Tests all four strategies, the data structures, error cases, and the factory function — 25 tests total.

### Key decisions

**Test the contract, not the implementation**
`test_chunk_size_respected` checks that no chunk exceeds the size limit — it doesn't check exact chunk text. `test_covers_all_content` checks that important words appear somewhere in the output — it doesn't check which chunk they're in. This makes tests robust to refactoring.

**`test_overlap_creates_overlap`**
```python
c = FixedSizeChunker(chunk_size=100, chunk_overlap=20)
result = c.chunk("a" * 200)
assert result.chunks[1].start_char < 100
```
Verifies that the second chunk starts before the end of the first — proving overlap is working. Uses a uniform string (`"a" * 200`) so character positions are predictable.

**`test_unknown_strategy_raises` and `test_overlap_gte_size_raises`**
Tests for error cases. A chunker with overlap ≥ size would loop forever or produce nonsense. The factory rejecting unknown strategy names surfaces typos immediately. Both tests verify that errors are caught early with clear messages rather than producing silently wrong output.

---

## `requirements.txt`

```
pdfplumber>=0.10.0    # optional — PDF reading
python-docx>=1.0.0   # optional — DOCX reading
tiktoken>=0.6.0      # optional — TokenChunker
pytest>=7.0          # optional — running tests
```

Zero required dependencies. The three most useful strategies (`fixed`, `sentence`, `recursive`) use only the Python stdlib. This means the library works out of the box in any Python 3.11+ environment — no pip install before you can start chunking.
