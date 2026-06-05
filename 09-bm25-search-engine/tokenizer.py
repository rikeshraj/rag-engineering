"""
Tokenizer

Converts raw text into a list of normalized tokens for indexing and search.

Pipeline:
    raw text → lowercase → remove punctuation → split → remove stopwords → stem

Why each step matters for BM25:
- Lowercase: "Python" and "python" should match
- Remove punctuation: "RAG." and "RAG" should match
- Stopwords: "the", "is", "a" appear in every document — they
  carry no signal and inflate term frequency counts
- Stemming: "retrieving", "retrieval", "retrieve" → "retriev"
  Maps word variants to a common root so they match each other
"""

import re
import string


# ------------------------------------------------------------------
# Stopwords
# ------------------------------------------------------------------

# Common English words that carry no discriminating signal.
# A term that appears in every document is useless for ranking —
# IDF pushes it toward 0, but filtering it entirely is faster.
STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "as", "is", "was", "are",
    "were", "been", "be", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall",
    "can", "not", "this", "that", "these", "those", "it", "its",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
    "their", "him", "her", "his", "what", "which", "who", "whom",
    "how", "when", "where", "why", "all", "each", "any", "more",
    "most", "than", "then", "so", "if", "up", "out", "about",
    "into", "through", "over", "after", "also", "just", "only",
    "both", "such", "there", "here", "no", "nor", "very", "one",
    "two", "three", "new", "other", "use", "used", "using",
})


# ------------------------------------------------------------------
# Stemmer — Porter Stemmer (simplified)
# ------------------------------------------------------------------

class SimpleStemmer:
    """
    A simplified Porter stemmer that handles the most common
    English suffixes. Not 100% accurate but good enough for
    search — the same rules apply to both indexed text and queries,
    so stemming errors cancel out.

    Full Porter Stemmer: https://tartarus.org/martin/PorterStemmer/
    We implement Steps 1a and 1b (the most impactful steps).
    """

    # Step 1a: plural and past tense
    STEP1A = [
        ("sses", "ss"),   # caresses → caress
        ("ies",  "i"),    # ponies → poni
        ("ss",   "ss"),   # caress → caress
        ("s",    ""),     # cats → cat
    ]

    # Step 1b: -ed, -ing
    STEP1B = [
        ("eed", "ee"),    # agreed → agree (if stem has vowel)
        ("ed",  ""),      # plastered → plaster
        ("ing", ""),      # motoring → motor
    ]

    # Step 2: common suffixes → shorter form
    STEP2 = [
        ("ational", "ate"),
        ("tional",  "tion"),
        ("enci",    "ence"),
        ("anci",    "ance"),
        ("izer",    "ize"),
        ("isation", "ize"),
        ("ization", "ize"),
        ("isation", "ise"),
        ("ational", "al"),
        ("alism",   "al"),
        ("aliti",   "al"),
        ("fulness", "ful"),
        ("ousness", "ous"),
        ("iveness", "ive"),
        ("ization", "ize"),
        ("ational", "ate"),
        ("ation",   "ate"),
        ("ator",    "ate"),
        ("alism",   "al"),
        ("ing",     ""),
        ("ment",    ""),
        ("ness",    ""),
        ("tion",    "t"),
        ("sion",    "s"),
        ("er",      ""),
        ("al",      ""),
        ("ic",      ""),
        ("ly",      ""),
    ]

    def _has_vowel(self, word: str) -> bool:
        return any(c in "aeiou" for c in word)

    def stem(self, word: str) -> str:
        if len(word) <= 2:
            return word

        # Step 1a
        for suffix, replacement in self.STEP1A:
            if word.endswith(suffix):
                word = word[: -len(suffix)] + replacement
                break

        # Step 1b
        for suffix, replacement in self.STEP1B:
            if word.endswith(suffix):
                stem = word[: -len(suffix)] + replacement
                if self._has_vowel(stem) and len(stem) >= 2:
                    word = stem
                break

        # Step 2 — only apply if word is long enough
        if len(word) > 5:
            for suffix, replacement in self.STEP2:
                if word.endswith(suffix):
                    candidate = word[: -len(suffix)] + replacement
                    if len(candidate) >= 3:
                        word = candidate
                        break

        return word


# ------------------------------------------------------------------
# Tokenizer
# ------------------------------------------------------------------

class Tokenizer:
    """
    Converts raw text to a list of normalized tokens.

    Parameters:
        remove_stopwords : filter out common English words (default: True)
        stem             : apply suffix stripping (default: True)
        min_token_len    : discard tokens shorter than this (default: 2)
    """

    # Match any character that is not a letter, digit, or hyphen
    # Hyphen kept so "state-of-the-art" → "state", "of", "the", "art"
    PUNCT_RE = re.compile(r"[^a-z0-9\-]")
    HYPHEN_RE = re.compile(r"-+")

    def __init__(
        self,
        remove_stopwords: bool = True,
        stem: bool = True,
        min_token_len: int = 2,
    ):
        self.remove_stopwords = remove_stopwords
        self.stem = stem
        self.min_token_len = min_token_len
        self._stemmer = SimpleStemmer() if stem else None

    def tokenize(self, text: str) -> list[str]:
        """Convert text to a list of normalized tokens."""
        if not text:
            return []

        # Lowercase
        text = text.lower()

        # Replace punctuation with space (keep hyphens for now)
        text = self.PUNCT_RE.sub(" ", text)

        # Replace hyphens with spaces
        text = self.HYPHEN_RE.sub(" ", text)

        # Split on whitespace
        tokens = text.split()

        # Filter short tokens
        tokens = [t for t in tokens if len(t) >= self.min_token_len]

        # Remove stopwords
        if self.remove_stopwords:
            tokens = [t for t in tokens if t not in STOPWORDS]

        # Stem
        if self._stemmer:
            tokens = [self._stemmer.stem(t) for t in tokens]

        # Final dedup of empty strings from stemming
        tokens = [t for t in tokens if t]

        return tokens

    def tokenize_query(self, query: str) -> list[str]:
        """
        Tokenize a search query. Same pipeline as documents —
        consistency is essential: a query token must match the
        indexed form of the same word.
        """
        return self.tokenize(query)
