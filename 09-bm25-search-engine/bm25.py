"""
BM25 — Best Match 25

The industry-standard keyword relevance ranking algorithm.
Used by Elasticsearch, Solr, Lucene, and most search engines.

BM25 improves on TF-IDF in two ways:

1. Term Frequency Saturation (k1 parameter)
   TF-IDF scores grow linearly with term frequency — a document
   mentioning "python" 100 times scores 100x higher than one
   mentioning it once. BM25 saturates: after a certain frequency,
   additional occurrences contribute diminishing returns.

2. Document Length Normalization (b parameter)
   Long documents naturally contain more terms. BM25 normalizes
   term frequency by document length relative to the corpus average.
   A term appearing 5 times in a 50-word doc scores higher than
   the same term appearing 5 times in a 500-word doc.

BM25 Formula:

    score(D, Q) = Σ IDF(qᵢ) × f(qᵢ, D) × (k1 + 1)
                              ─────────────────────────────────────────
                              f(qᵢ, D) + k1 × (1 - b + b × |D| / avgdl)

Where:
    qᵢ      — each query term
    f(qᵢ,D) — term frequency of qᵢ in document D
    |D|     — length of D in tokens
    avgdl   — average document length across corpus
    k1      — saturation parameter (typically 1.2–2.0, default 1.5)
    b       — length normalization (0=none, 1=full, default 0.75)

IDF formula (with smoothing to prevent negative values):

    IDF(q) = ln((N - n(q) + 0.5) / (n(q) + 0.5) + 1)

Where:
    N    — total documents in corpus
    n(q) — documents containing term q
"""

import math
from dataclasses import dataclass, field

from index import InvertedIndex, IndexedDocument


# ------------------------------------------------------------------
# Result
# ------------------------------------------------------------------

@dataclass
class BM25Result:
    """A single search result with its BM25 score."""
    doc_id: int
    score: float
    document: IndexedDocument
    matched_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc_id":        self.doc_id,
            "score":         round(self.score, 6),
            "matched_terms": self.matched_terms,
            **self.document.to_dict(),
        }


# ------------------------------------------------------------------
# BM25 Scorer
# ------------------------------------------------------------------

class BM25:
    """
    BM25 scorer over an InvertedIndex.

    Parameters:
        k1 : term frequency saturation (1.2–2.0, default 1.5)
             Higher = more weight to repeated terms
             Lower = faster saturation (frequency matters less)
        b  : length normalization (0.0–1.0, default 0.75)
             0.0 = no normalization (length ignored)
             1.0 = full normalization (length fully penalized)
    """

    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75):
        self.index = index
        self.k1 = k1
        self.b = b

    # ------------------------------------------------------------------
    # IDF
    # ------------------------------------------------------------------

    def idf(self, term: str) -> float:
        """
        Inverse Document Frequency with smoothing.

        IDF = ln((N - n + 0.5) / (n + 0.5) + 1)

        The +1 at the end prevents negative IDF for very common terms.
        Without it, a term in >50% of documents gets negative IDF,
        causing its presence to hurt the score — counterintuitive.

        The 0.5 smoothing prevents division by zero and reduces the
        extreme weight given to very rare terms.
        """
        N = self.index.num_documents
        n = self.index.get_document_freq(term)

        if N == 0 or n == 0:
            return 0.0

        return math.log((N - n + 0.5) / (n + 0.5) + 1)

    # ------------------------------------------------------------------
    # Term score
    # ------------------------------------------------------------------

    def term_score(self, term: str, doc_id: int, doc_length: int) -> float:
        """
        BM25 score contribution of a single term in a single document.

        term_freq * (k1 + 1)
        ──────────────────────────────────────────────────────────────
        term_freq + k1 * (1 - b + b * doc_length / avg_doc_length)
        """
        postings = self.index.get_postings(term)
        tf = postings.get(doc_id, 0)

        if tf == 0:
            return 0.0

        avgdl = self.index.avg_document_length
        if avgdl == 0:
            return 0.0

        numerator   = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / avgdl)

        return self.idf(term) * (numerator / denominator)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_tokens: list[str],
        k: int = 10,
        collection: str | None = None,
        min_score: float = 0.0,
    ) -> list[BM25Result]:
        """
        Score all documents against a query and return top-k.

        Steps:
        1. Find candidate documents — union of posting lists
           for all query terms (only docs containing at least
           one query term are candidates)
        2. Score each candidate with BM25
        3. Filter by collection if specified
        4. Sort by score descending, return top-k

        Using posting lists to find candidates is what makes this
        fast — we never look at documents that share no terms with
        the query.

        Parameters:
            query_tokens : pre-tokenized query terms
            k            : max results to return
            collection   : restrict search to this collection
            min_score    : discard results below this score
        """
        if not query_tokens or self.index.num_documents == 0:
            return []

        # 1. Find candidate doc_ids from posting lists
        candidate_ids: set[int] = set()
        for term in query_tokens:
            postings = self.index.get_postings(term)
            candidate_ids.update(postings.keys())

        if not candidate_ids:
            return []

        # 2. Filter by collection
        if collection:
            collection_ids = self.index.get_documents_in_collection(collection)
            candidate_ids &= collection_ids   # intersection

        if not candidate_ids:
            return []

        # 3. Score each candidate
        results: list[BM25Result] = []
        query_term_set = set(query_tokens)

        for doc_id in candidate_ids:
            doc = self.index.get_document(doc_id)
            if not doc:
                continue

            # Sum BM25 contribution of each query term
            total_score = 0.0
            matched: list[str] = []

            for term in query_term_set:
                ts = self.term_score(term, doc_id, doc.token_count)
                if ts > 0:
                    total_score += ts
                    matched.append(term)

            if total_score >= min_score:
                results.append(BM25Result(
                    doc_id=doc_id,
                    score=total_score,
                    document=doc,
                    matched_terms=matched,
                ))

        # 4. Sort by score descending, return top-k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]
