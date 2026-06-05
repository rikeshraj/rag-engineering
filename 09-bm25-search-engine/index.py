"""
Inverted Index

The core data structure behind every search engine.

A forward index maps:    document_id → list of terms
An inverted index maps:  term        → list of document_ids

The inverted index is what makes full-text search fast.
Instead of scanning every document for a query term,
we look up the term and immediately get the list of
documents that contain it.

Structure:
    {
        "retriev": {         ← stemmed token
            1: 3,            ← doc_id: term_frequency
            4: 1,
            7: 2,
        },
        "generat": {
            1: 1,
            2: 5,
        },
        ...
    }

Plus per-document metadata:
    {
        1: {"content": "...", "tokens": [...], "length": 42, ...},
        2: {...},
    }
"""

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ------------------------------------------------------------------
# Document metadata
# ------------------------------------------------------------------

@dataclass
class IndexedDocument:
    """Metadata stored per document in the index."""
    doc_id: int
    content: str
    token_count: int          # number of tokens (after stopword removal)
    source: str = ""
    collection: str = "default"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doc_id":      self.doc_id,
            "content":     self.content,
            "token_count": self.token_count,
            "source":      self.source,
            "collection":  self.collection,
            "metadata":    self.metadata,
        }


# ------------------------------------------------------------------
# Inverted Index
# ------------------------------------------------------------------

class InvertedIndex:
    """
    In-memory inverted index with optional disk persistence.

    Supports:
    - add_document()       : index a new document
    - remove_document()    : remove a document from the index
    - get_postings()       : get {doc_id: term_freq} for a term
    - get_document_freq()  : how many docs contain a term
    - save() / load()      : persist to / restore from JSON file
    """

    def __init__(self):
        # term → {doc_id: term_frequency}
        self._index: dict[str, dict[int, int]] = {}

        # doc_id → IndexedDocument
        self._documents: dict[int, IndexedDocument] = {}

        # Auto-incrementing document ID
        self._next_id: int = 1

        # Running total of all token counts (for avgdl calculation)
        self._total_tokens: int = 0

    # ------------------------------------------------------------------
    # Index operations
    # ------------------------------------------------------------------

    def add_document(
        self,
        content: str,
        tokens: list[str],
        source: str = "",
        collection: str = "default",
        metadata: dict | None = None,
    ) -> int:
        """
        Add a document to the index. Returns the assigned doc_id.

        tokens: pre-tokenized list from Tokenizer.tokenize()
        """
        doc_id = self._next_id
        self._next_id += 1

        # Count term frequencies in this document
        term_counts = Counter(tokens)

        # Update inverted index
        for term, freq in term_counts.items():
            if term not in self._index:
                self._index[term] = {}
            self._index[term][doc_id] = freq

        # Store document metadata
        self._documents[doc_id] = IndexedDocument(
            doc_id=doc_id,
            content=content,
            token_count=len(tokens),
            source=source,
            collection=collection,
            metadata=metadata or {},
        )

        self._total_tokens += len(tokens)
        return doc_id

    def remove_document(self, doc_id: int) -> bool:
        """
        Remove a document from the index.
        Cleans up all postings lists that referenced this document.
        Returns True if document existed.
        """
        if doc_id not in self._documents:
            return False

        doc = self._documents[doc_id]
        self._total_tokens -= doc.token_count

        # Remove this doc from every postings list
        # Track which terms become empty so we can remove them
        empty_terms = []
        for term, postings in self._index.items():
            if doc_id in postings:
                del postings[doc_id]
                if not postings:
                    empty_terms.append(term)

        # Remove empty postings lists
        for term in empty_terms:
            del self._index[term]

        del self._documents[doc_id]
        return True

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def get_postings(self, term: str) -> dict[int, int]:
        """
        Return {doc_id: term_frequency} for a term.
        Returns empty dict if term not in index.
        """
        return self._index.get(term, {})

    def get_document_freq(self, term: str) -> int:
        """Number of documents containing this term (df)."""
        return len(self._index.get(term, {}))

    def get_document(self, doc_id: int) -> IndexedDocument | None:
        return self._documents.get(doc_id)

    def get_documents_in_collection(self, collection: str) -> set[int]:
        """Return set of doc_ids belonging to a collection."""
        return {
            doc_id
            for doc_id, doc in self._documents.items()
            if doc.collection == collection
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def num_documents(self) -> int:
        return len(self._documents)

    @property
    def num_terms(self) -> int:
        return len(self._index)

    @property
    def avg_document_length(self) -> float:
        """
        Average token count across all documents.
        Used by BM25 for length normalization.
        """
        if self.num_documents == 0:
            return 0.0
        return self._total_tokens / self.num_documents

    def stats(self) -> dict:
        collections: dict[str, int] = {}
        for doc in self._documents.values():
            collections[doc.collection] = collections.get(doc.collection, 0) + 1

        return {
            "num_documents":       self.num_documents,
            "num_terms":           self.num_terms,
            "avg_document_length": round(self.avg_document_length, 2),
            "total_tokens":        self._total_tokens,
            "collections":         collections,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """
        Serialize the index to a JSON file.

        The index dict has integer doc_ids as keys. JSON requires
        string keys, so we convert int → str on save and back on load.
        """
        data = {
            "next_id":       self._next_id,
            "total_tokens":  self._total_tokens,
            "documents": {
                str(doc_id): doc.to_dict()
                for doc_id, doc in self._documents.items()
            },
            "index": {
                term: {str(k): v for k, v in postings.items()}
                for term, postings in self._index.items()
            },
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: Path) -> None:
        """Restore the index from a JSON file."""
        if not path.exists():
            raise FileNotFoundError(f"Index file not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))

        self._next_id = data["next_id"]
        self._total_tokens = data["total_tokens"]

        self._documents = {
            int(doc_id): IndexedDocument(**doc_data)
            for doc_id, doc_data in data["documents"].items()
        }

        self._index = {
            term: {int(k): v for k, v in postings.items()}
            for term, postings in data["index"].items()
        }

    def clear(self) -> None:
        """Reset the index to empty state."""
        self._index.clear()
        self._documents.clear()
        self._next_id = 1
        self._total_tokens = 0
