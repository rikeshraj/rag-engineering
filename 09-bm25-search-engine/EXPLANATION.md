# BM25 Search Engine — File-by-File Breakdown

A complete explanation of every file, what it does, why it was built that way, and the key decisions made.

---

## Project Structure

```
09-bm25-search-engine/
├── main.py       # FastAPI routes
├── engine.py     # SearchEngine facade
├── bm25.py       # BM25 scoring
├── index.py      # InvertedIndex data structure
├── tokenizer.py  # Text preprocessing
├── models.py     # Pydantic models
└── auth.py       # API key auth
```

### How the files connect

```
main.py
  └── engine.py         ← single entry point for all operations
        ├── tokenizer.py  ← text → tokens
        ├── index.py      ← tokens → inverted index
        └── bm25.py       ← index + query → ranked scores
```

Each layer has one responsibility. `main.py` never touches the index directly. `bm25.py` never tokenizes text. `tokenizer.py` knows nothing about scoring. This separation means each component can be tested independently and swapped without touching the others.

---

## `tokenizer.py`

### What it does
Converts raw text into a normalized list of tokens ready for indexing. Same pipeline applied at both index time and query time — consistency is essential.

### Tokenization pipeline

```
"Python is great for RAG systems!"
   → lowercase:         "python is great for rag systems!"
   → remove punct:      "python is great for rag systems"
   → split:             ["python", "is", "great", "for", "rag", "systems"]
   → remove stopwords:  ["python", "great", "rag", "systems"]
   → stem:              ["python", "great", "rag", "system"]
```

**Why stopwords matter for BM25:**
"the", "is", "a" appear in virtually every document. Their IDF is near zero because they provide no discriminating signal. Filtering them before indexing reduces index size and speeds up search with zero loss in quality.

**Why stemming matters for recall:**
Without stemming, "retrieve", "retrieval", "retrieving" are three different terms. A query for "retrieval" misses documents that say "retrieving". The stemmer maps all three to "retriev" — same index entry, better recall.

### `SimpleStemmer` — the Porter algorithm (simplified)

The full Porter Stemmer has 5 steps with complex rules. This implementation covers Steps 1a, 1b, and 2 — the most impactful rules that handle plurals, -ing/-ed, and common suffixes:

```python
STEP1A = [
    ("sses", "ss"),   # caresses → caress
    ("ies",  "i"),    # ponies → poni
    ("s",    ""),     # cats → cat
]

STEP1B = [
    ("ing", ""),      # motoring → motor
    ("ed",  ""),      # plastered → plaster
]
```

**Why not use NLTK's Porter Stemmer?**
NLTK is a large dependency. The simplified stemmer handles 95% of real-world English correctly. Since the same stemmer runs on both documents and queries, stemming errors cancel out — "retriev" in documents matches "retriev" in queries even if "retriev" isn't a real word.

**Why `frozenset` for stopwords?**
`in` operator on a `frozenset` is O(1) — hash lookup. On a `list` it's O(n) — linear scan. With thousands of tokens being filtered, this matters. `frozenset` is also immutable — no accidental modification.

---

## `index.py`

### What it does
The inverted index data structure. Maps terms to posting lists, stores per-document metadata, and handles persistence.

### The inverted index structure

```python
_index: dict[str, dict[int, int]]
# term → {doc_id: term_frequency}

{
    "retriev": {1: 3, 4: 1, 7: 2},
    "generat": {1: 1, 2: 5},
    "python":  {1: 2, 3: 1, 4: 4},
}
```

**Why this structure?**
The inverted index is the key insight of modern search. Without it, searching for "python" requires scanning every document's content. With it, you look up "python" in the dict and immediately get `{1: 2, 3: 1, 4: 4}` — the exact documents containing it and how many times. Search becomes O(1) lookup + O(k) scoring instead of O(n × doc_length) scanning.

**Why nested dict instead of `{term: list[doc_id]}`?**
Storing term frequencies (`doc_id: freq`) instead of just doc_ids enables the BM25 TF component. A flat list would require a second data structure to track frequencies.

### `add_document()` — building the index

```python
term_counts = Counter(tokens)  # {"python": 2, "rag": 1}
for term, freq in term_counts.items():
    if term not in self._index:
        self._index[term] = {}
    self._index[term][doc_id] = freq
```

`Counter` computes term frequencies in one pass. Then each term's posting list is updated with the new doc_id and frequency. The entire operation is O(unique_terms) — fast even for large documents.

### `remove_document()` — cleaning up

```python
empty_terms = []
for term, postings in self._index.items():
    if doc_id in postings:
        del postings[doc_id]
        if not postings:
            empty_terms.append(term)

for term in empty_terms:
    del self._index[term]
```

Two-pass deletion: first collect terms that became empty, then delete them. Can't delete during iteration — modifying a dict while iterating raises `RuntimeError`. The two-pass approach avoids this. Empty posting lists are removed to prevent the index from growing indefinitely.

### Persistence — JSON with int→str key conversion

```python
def save(self, path: Path) -> None:
    data = {
        "index": {
            term: {str(k): v for k, v in postings.items()}
            for term, postings in self._index.items()
        },
    }
    path.write_text(json.dumps(data, indent=2))

def load(self, path: Path) -> None:
    self._index = {
        term: {int(k): v for k, v in postings.items()}
        for term, postings in data["index"].items()
    }
```

**Why the int→str conversion?**
JSON requires string keys — `{1: 2}` would serialize as `{"1": 2}`. On load, `"1"` is a string, not the integer `1` we need for doc_id lookups. Converting to strings on save and back to integers on load handles this correctly. The docstring in `save()` explicitly calls this out.

### `avg_document_length` — running total

```python
self._total_tokens: int = 0

def add_document(..., tokens):
    ...
    self._total_tokens += len(tokens)

@property
def avg_document_length(self) -> float:
    return self._total_tokens / self.num_documents
```

Instead of summing all document lengths on every query (O(n)), we maintain a running total updated on every insert and delete. `avg_document_length` is O(1) — critical since BM25 uses it for every single scored document.

---

## `bm25.py`

### What it does
Implements the BM25 scoring formula over an `InvertedIndex`.

### IDF formula

```python
def idf(self, term: str) -> float:
    N = self.index.num_documents
    n = self.index.get_document_freq(term)
    return math.log((N - n + 0.5) / (n + 0.5) + 1)
```

**Breaking down the formula:**
- `N` = total documents, `n` = documents containing term
- `(N - n + 0.5) / (n + 0.5)` = ratio of docs without term to docs with term
- `+1` inside the log prevents negative IDF for terms in >50% of docs
- `0.5` smoothing prevents division by zero and dampens extreme weights for very rare terms

**Why +1 matters:**
Without it, a term in 60% of documents gets `log(0.4/0.6) = log(0.667) = -0.4`. Negative IDF means the term's presence hurts the score — counterintuitive. The +1 shifts all IDFs to be non-negative.

### Term score formula

```python
def term_score(self, term, doc_id, doc_length):
    tf = postings.get(doc_id, 0)
    avgdl = self.index.avg_document_length

    numerator   = tf * (self.k1 + 1)
    denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / avgdl)

    return self.idf(term) * (numerator / denominator)
```

**The k1 parameter — saturation:**
As `tf` → ∞, the fraction → `(k1 + 1) / k1`. This is the saturation ceiling. With k1=1.5, max boost = 2.5/1.5 = 1.67×. A document mentioning a term 100 times scores at most 1.67× a document mentioning it once. Compare to TF-IDF where 100 mentions = 100× score.

**The b parameter — length normalization:**
`doc_length / avgdl` is the relative length of this document. When b=0.75, long documents get penalized by 75% of their relative length excess. A document 2× the average length scores as if its TF were lower.

**Why b=0.75 and k1=1.5 are the defaults:**
These are the values that consistently perform best across many benchmark datasets (TREC, etc.). They're not theoretically derived — they're empirically validated over decades of IR research.

### Search algorithm

```python
# 1. Collect candidates from posting lists
candidate_ids: set[int] = set()
for term in query_tokens:
    postings = self.index.get_postings(term)
    candidate_ids.update(postings.keys())

# 2. Score each candidate
for doc_id in candidate_ids:
    total_score = sum(self.term_score(term, doc_id, doc.token_count)
                      for term in query_term_set)

# 3. Sort and return top-k
results.sort(key=lambda r: r.score, reverse=True)
return results[:k]
```

**Why collect candidates from posting lists first?**
Only documents that contain at least one query term can score above 0. Posting lists give us exactly those documents — we never score documents that share no terms with the query. This is what makes search O(matching_docs) instead of O(all_docs).

---

## `engine.py`

### What it does
The facade — a single class that combines `Tokenizer`, `InvertedIndex`, and `BM25` into a simple public API.

### The Facade pattern

```python
class SearchEngine:
    def __init__(self, k1=1.5, b=0.75, ...):
        self.tokenizer = Tokenizer(...)
        self.index = InvertedIndex()
        self.bm25 = BM25(self.index, k1=k1, b=b)

    def add_document(self, content, ...):
        tokens = self.tokenizer.tokenize(content)
        return self.index.add_document(content, tokens, ...)

    def search(self, query, k=10, ...):
        tokens = self.tokenizer.tokenize_query(query)
        return self.bm25.search(tokens, k=k, ...)
```

Callers only interact with `SearchEngine`. They never call `Tokenizer.tokenize()` directly — the engine ensures tokenization always runs before indexing or searching. This makes it impossible to accidentally search without tokenizing.

**Why `add_batch` loops instead of batch-optimizing?**
The bottleneck for indexing is dict operations — O(unique_terms per doc). A batch doesn't change this. The loop is simple, readable, and correct. Optimization would only matter at very high document volumes where you'd parallelize with multiprocessing.

---

## `main.py`

### Key decisions

**Auto-save on shutdown via lifespan:**
```python
@asynccontextmanager
async def lifespan(app):
    if INDEX_PATH.exists():
        engine.load(INDEX_PATH)   # restore on startup
    yield
    engine.save(INDEX_PATH)       # persist on shutdown
```
The index is in-memory. Without auto-save, every restart loses all indexed documents. Auto-loading on startup means the engine resumes exactly where it left off — zero manual intervention needed.

**`query_tokens` in search response:**
```json
{
  "query": "ranking algorithm elasticsearch",
  "query_tokens": ["rank", "algorithm", "elasticsearch"]
}
```
Showing the tokenized query is valuable for debugging — it lets you see exactly what the engine searched for. If stemming converts "retrieving" to "retriev" and your documents use "retriev", you can verify the match immediately.

**`matched_terms` per result:**
Each search result shows which query terms matched in that document. This is useful for understanding why a document ranked where it did, and for building highlighted snippet previews in a UI.

**BM25 parameters from environment:**
```python
engine = SearchEngine(
    k1=float(os.getenv("BM25_K1", "1.5")),
    b=float(os.getenv("BM25_B", "0.75")),
)
```
Allows tuning without code changes. Different document corpora perform best with different k1/b values — short snippets vs long articles, technical docs vs prose. Environment config makes this tunable at deployment time.

---

## `tests/test_bm25.py`

### Coverage across all layers

Tests are organized by component — `TestStemmer`, `TestTokenizer`, `TestInvertedIndex`, `TestBM25`, `TestSearchEngine`, then API routes. This gives you a clear failure signal: if `TestInvertedIndex` passes but `TestBM25` fails, the bug is in the scoring, not the data structure.

### Key test: `test_idf_rare_term`

```python
def test_idf_rare_term(self):
    self.idx.add_document("d1", ["python", "common"])
    self.idx.add_document("d2", ["common"])
    self.idx.add_document("d3", ["common"])
    idf_common = self.bm25.idf("common")
    idf_rare   = self.bm25.idf("python")
    assert idf_rare > idf_common
```

This verifies the core property of IDF: rare terms should score higher than common ones. "python" appears in 1/3 documents; "common" in 3/3. If IDF is implemented correctly, `idf_rare > idf_common`.

### Key test: `test_results_sorted_by_score`

```python
scores = [r.score for r in results]
assert scores == sorted(scores, reverse=True)
```

Verifies that results come back highest-score-first. A subtle off-by-one in the sort comparator could reverse the order — this test catches it.

### Key test: `test_save_and_load`

```python
self.idx.add_document("doc1", ["python", "rag"])
path = tmp_path / "test_index.json"
self.idx.save(path)

idx2 = InvertedIndex()
idx2.load(path)
assert idx2.get_document_freq("python") == 1
assert idx2.get_postings("llm")[2] == 1
```

Verifies that the int→str→int key conversion in JSON serialization works correctly. This is the most common serialization bug — `"2"` (string) vs `2` (integer) as a dict key.
