"""
SearchEngine

Ties together Tokenizer, InvertedIndex, and BM25.
This is the public API for the search engine — callers
only need this class, not the internals.

Usage:
    engine = SearchEngine()
    engine.add_document("RAG combines retrieval with generation.", source="intro.txt")
    engine.add_document("Vector embeddings represent semantic meaning.")

    results = engine.search("retrieval generation", k=5)
    for r in results:
        print(r.score, r.document.content)

    engine.save(Path("index.json"))
    engine.load(Path("index.json"))
"""

from dataclasses import dataclass, field
from pathlib import Path

from bm25 import BM25, BM25Result
from index import InvertedIndex
from tokenizer import Tokenizer


class SearchEngine:
    """
    Complete BM25 search engine.

    Combines:
    - Tokenizer  : text → normalized tokens
    - InvertedIndex : tokens → fast lookup structure
    - BM25       : query → ranked results

    All three use the same tokenization settings so indexed tokens
    and query tokens always match.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        remove_stopwords: bool = True,
        stem: bool = True,
    ):
        self.tokenizer = Tokenizer(
            remove_stopwords=remove_stopwords,
            stem=stem,
        )
        self.index = InvertedIndex()
        self.bm25 = BM25(self.index, k1=k1, b=b)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add_document(
        self,
        content: str,
        source: str = "",
        collection: str = "default",
        metadata: dict | None = None,
    ) -> int:
        """
        Tokenize and index a document. Returns the assigned doc_id.
        """
        tokens = self.tokenizer.tokenize(content)
        return self.index.add_document(
            content=content,
            tokens=tokens,
            source=source,
            collection=collection,
            metadata=metadata,
        )

    def add_batch(self, documents: list[dict]) -> list[int]:
        """
        Index multiple documents. Each dict must have 'content'.
        Optional: 'source', 'collection', 'metadata'.
        Returns list of assigned doc_ids.
        """
        doc_ids = []
        for doc in documents:
            doc_id = self.add_document(
                content=doc["content"],
                source=doc.get("source", ""),
                collection=doc.get("collection", "default"),
                metadata=doc.get("metadata"),
            )
            doc_ids.append(doc_id)
        return doc_ids

    def remove_document(self, doc_id: int) -> bool:
        """Remove a document from the index. Returns True if found."""
        return self.index.remove_document(doc_id)

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 10,
        collection: str | None = None,
        min_score: float = 0.0,
    ) -> list[BM25Result]:
        """
        Search the index for documents matching the query.

        The query is tokenized with the same pipeline as indexed
        documents — ensuring consistency between index and search time.
        """
        query_tokens = self.tokenizer.tokenize_query(query)
        return self.bm25.search(
            query_tokens=query_tokens,
            k=k,
            collection=collection,
            min_score=min_score,
        )

    def get_document(self, doc_id: int):
        """Retrieve a document by ID."""
        return self.index.get_document(doc_id)

    # ------------------------------------------------------------------
    # Stats / Persistence
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return self.index.stats()

    def save(self, path: Path) -> None:
        """Persist the index to disk as JSON."""
        self.index.save(path)

    def load(self, path: Path) -> None:
        """Restore the index from a JSON file."""
        self.index.load(path)

    def clear(self) -> None:
        """Reset the index."""
        self.index.clear()
