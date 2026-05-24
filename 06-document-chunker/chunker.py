"""
Chunker

Splits documents into chunks ready for embedding.
Four strategies — each suited to different content types.

Strategies:
    fixed       — split every N characters with overlap
    sentence    — split on sentence boundaries
    recursive   — try paragraphs → lines → words → characters
    token       — split by token count (requires tiktoken)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class Chunk:
    """
    A single chunk of text with metadata.

    text        — the actual chunk content
    index       — position of this chunk in the document (0-based)
    start_char  — character offset where this chunk starts in the original
    end_char    — character offset where this chunk ends
    source      — filename or identifier of the source document
    metadata    — any extra info (page number, section, etc.)
    """
    text: str
    index: int
    start_char: int
    end_char: int
    source: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        """
        Rough token estimate without tiktoken.
        Rule of thumb: 1 token ≈ 4 characters for English text.
        """
        return len(self.text) // 4

    def to_dict(self) -> dict:
        return {
            "index":          self.index,
            "text":           self.text,
            "start_char":     self.start_char,
            "end_char":       self.end_char,
            "char_count":     len(self.text),
            "token_estimate": self.token_estimate,
            "source":         self.source,
            "metadata":       self.metadata,
        }


@dataclass
class ChunkResult:
    """Full result of a chunking operation."""
    chunks: list[Chunk]
    strategy: str
    source: str
    total_chars: int
    chunk_size: int
    chunk_overlap: int

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)

    @property
    def avg_chunk_size(self) -> float:
        if not self.chunks:
            return 0.0
        return round(sum(len(c.text) for c in self.chunks) / len(self.chunks), 1)

    def to_dict(self) -> dict:
        return {
            "source":        self.source,
            "strategy":      self.strategy,
            "chunk_size":    self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "total_chars":   self.total_chars,
            "total_chunks":  self.total_chunks,
            "avg_chunk_size": self.avg_chunk_size,
            "chunks":        [c.to_dict() for c in self.chunks],
        }


# ------------------------------------------------------------------
# Base class
# ------------------------------------------------------------------

class BaseChunker:
    """
    Base class for all chunking strategies.

    All chunkers share:
    - chunk_size   : target size of each chunk (in characters or tokens)
    - chunk_overlap: how many characters to repeat between chunks
    - source       : label for where the text came from
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        source: str = "",
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than "
                f"chunk_size ({chunk_size})"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.source = source

    def chunk(self, text: str) -> ChunkResult:
        raise NotImplementedError

    def _build_result(
        self, chunks: list[Chunk], text: str, strategy: str
    ) -> ChunkResult:
        return ChunkResult(
            chunks=chunks,
            strategy=strategy,
            source=self.source,
            total_chars=len(text),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    def _make_chunks_from_splits(
        self, splits: list[str], text: str
    ) -> list[Chunk]:
        """
        Given a list of text splits, build Chunk objects with correct
        start/end character offsets into the original text.
        """
        chunks = []
        cursor = 0
        for i, split in enumerate(splits):
            # Find where this split occurs in original text
            start = text.find(split, cursor)
            if start == -1:
                start = cursor
            end = start + len(split)
            chunks.append(Chunk(
                text=split,
                index=i,
                start_char=start,
                end_char=end,
                source=self.source,
            ))
            cursor = max(cursor, end - self.chunk_overlap)
        return chunks


# ------------------------------------------------------------------
# Strategy 1: Fixed Size
# ------------------------------------------------------------------

class FixedSizeChunker(BaseChunker):
    """
    Splits text into fixed-size character windows with overlap.

    Simplest strategy. Fast and predictable. Does not respect
    word or sentence boundaries — may split mid-word.

    Best for: uniform text where content boundaries don't matter,
              quick baseline, testing other components.

    chunk_size    : number of characters per chunk
    chunk_overlap : characters repeated at the start of next chunk
    """

    def chunk(self, text: str) -> ChunkResult:
        text = text.strip()
        if not text:
            return self._build_result([], text, "fixed")

        splits = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            splits.append(text[start:end])
            # Move forward by chunk_size minus overlap
            start += self.chunk_size - self.chunk_overlap

        chunks = []
        pos = 0
        for i, split in enumerate(splits):
            start_char = pos
            end_char = pos + len(split)
            chunks.append(Chunk(
                text=split,
                index=i,
                start_char=start_char,
                end_char=end_char,
                source=self.source,
            ))
            pos += self.chunk_size - self.chunk_overlap

        return self._build_result(chunks, text, "fixed")


# ------------------------------------------------------------------
# Strategy 2: Sentence-aware
# ------------------------------------------------------------------

class SentenceChunker(BaseChunker):
    """
    Splits text into chunks that respect sentence boundaries.

    Accumulates sentences until chunk_size is reached, then starts
    a new chunk — backtracking by chunk_overlap characters.

    Best for: prose, articles, reports where sentence integrity matters.
              Produces more natural chunks for embedding.

    chunk_size    : max characters per chunk
    chunk_overlap : characters to carry over into next chunk
    """

    # Sentence boundary pattern:
    # End of sentence punctuation (. ! ?) followed by whitespace + capital letter
    # or end of string. Uses lookahead to not consume the capital letter.
    SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$", re.MULTILINE)

    def chunk(self, text: str) -> ChunkResult:
        text = text.strip()
        if not text:
            return self._build_result([], text, "sentence")

        sentences = self._split_sentences(text)
        chunks = self._merge_sentences(sentences, text)
        return self._build_result(chunks, text, "sentence")

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into individual sentences."""
        parts = self.SENTENCE_END.split(text)
        # Clean and filter empty parts
        return [s.strip() for s in parts if s.strip()]

    def _merge_sentences(self, sentences: list[str], original: str) -> list[Chunk]:
        """
        Merge sentences into chunks up to chunk_size.
        When a chunk is full, carry overlap into the next chunk.
        """
        chunks = []
        current_sentences: list[str] = []
        current_len = 0
        chunk_index = 0
        char_cursor = 0

        for sentence in sentences:
            sentence_len = len(sentence) + 1  # +1 for space separator

            # If adding this sentence exceeds chunk_size, flush current chunk
            if current_len + sentence_len > self.chunk_size and current_sentences:
                chunk_text = " ".join(current_sentences)
                start = original.find(chunk_text, max(0, char_cursor - len(chunk_text)))
                if start == -1:
                    start = char_cursor

                chunks.append(Chunk(
                    text=chunk_text,
                    index=chunk_index,
                    start_char=start,
                    end_char=start + len(chunk_text),
                    source=self.source,
                ))
                chunk_index += 1
                char_cursor = start + len(chunk_text)

                # Build overlap: keep sentences from the end that fit in overlap
                overlap_sentences = []
                overlap_len = 0
                for s in reversed(current_sentences):
                    if overlap_len + len(s) + 1 <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break
                current_sentences = overlap_sentences
                current_len = overlap_len

            current_sentences.append(sentence)
            current_len += sentence_len

        # Flush remaining sentences
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            start = original.find(chunk_text, max(0, char_cursor - len(chunk_text)))
            if start == -1:
                start = char_cursor
            chunks.append(Chunk(
                text=chunk_text,
                index=chunk_index,
                start_char=start,
                end_char=start + len(chunk_text),
                source=self.source,
            ))

        return chunks


# ------------------------------------------------------------------
# Strategy 3: Recursive
# ------------------------------------------------------------------

class RecursiveChunker(BaseChunker):
    """
    Recursively splits text using a priority list of separators.

    Tries to split on paragraph boundaries first. If chunks are still
    too large, splits on newlines. Then sentences. Then words.
    Then individual characters as a last resort.

    This is the approach used by LangChain's RecursiveCharacterTextSplitter.

    Best for: mixed content (code + prose), structured documents,
              general-purpose chunking when you're unsure.

    chunk_size    : max characters per chunk
    chunk_overlap : characters to carry over into next chunk
    separators    : priority list of split points (default works for most text)
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        source: str = "",
        separators: list[str] | None = None,
    ):
        super().__init__(chunk_size, chunk_overlap, source)
        self.separators = separators or self.DEFAULT_SEPARATORS

    def chunk(self, text: str) -> ChunkResult:
        text = text.strip()
        if not text:
            return self._build_result([], text, "recursive")

        splits = self._split_recursive(text, self.separators)
        splits = self._merge_splits(splits)
        chunks = self._make_chunks_from_splits(splits, text)
        return self._build_result(chunks, text, "recursive")

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """
        Try each separator in order. If text fits in chunk_size, return it.
        Otherwise split and recurse on each piece.
        """
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            # No more separators — hard split by character
            return [
                text[i:i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
            ]

        separator = separators[0]
        remaining_seps = separators[1:]

        if separator == "":
            # Character-level split
            return [
                text[i:i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
            ]

        parts = text.split(separator)
        result = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(part) <= self.chunk_size:
                result.append(part)
            else:
                # This part is still too big — recurse with next separator
                result.extend(self._split_recursive(part, remaining_seps))

        return result

    def _merge_splits(self, splits: list[str]) -> list[str]:
        """
        Merge small splits into chunks up to chunk_size,
        carrying chunk_overlap into the next chunk.
        """
        merged = []
        current: list[str] = []
        current_len = 0

        for split in splits:
            split_len = len(split)

            if current_len + split_len + 1 > self.chunk_size and current:
                merged.append(" ".join(current))

                # Build overlap from end of current
                overlap: list[str] = []
                overlap_len = 0
                for s in reversed(current):
                    if overlap_len + len(s) + 1 <= self.chunk_overlap:
                        overlap.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break
                current = overlap
                current_len = overlap_len

            current.append(split)
            current_len += split_len + 1

        if current:
            merged.append(" ".join(current))

        return merged


# ------------------------------------------------------------------
# Strategy 4: Token-based
# ------------------------------------------------------------------

class TokenChunker(BaseChunker):
    """
    Splits text by token count instead of character count.

    Uses tiktoken to count tokens the same way LLMs do.
    More accurate than character-based chunking for staying within
    context window limits.

    chunk_size    : max TOKENS per chunk (not characters)
    chunk_overlap : tokens to carry over into next chunk
    model         : tiktoken encoding to use (default: cl100k_base — GPT-4/Claude)

    Requires: pip install tiktoken
    """

    def __init__(
        self,
        chunk_size: int = 256,
        chunk_overlap: int = 20,
        source: str = "",
        model: str = "cl100k_base",
    ):
        super().__init__(chunk_size, chunk_overlap, source)
        self.model = model
        self._enc = None

    def _get_encoder(self):
        if self._enc is None:
            try:
                import tiktoken
                self._enc = tiktoken.get_encoding(self.model)
            except ImportError:
                raise ImportError(
                    "tiktoken is required for TokenChunker.\n"
                    "Install it with: pip install tiktoken"
                )
        return self._enc

    def _count_tokens(self, text: str) -> int:
        return len(self._get_encoder().encode(text))

    def _decode_tokens(self, tokens: list[int]) -> str:
        return self._get_encoder().decode(tokens)

    def chunk(self, text: str) -> ChunkResult:
        text = text.strip()
        if not text:
            return self._build_result([], text, "token")

        enc = self._get_encoder()
        all_tokens = enc.encode(text)

        splits = []
        start = 0
        while start < len(all_tokens):
            end = min(start + self.chunk_size, len(all_tokens))
            token_slice = all_tokens[start:end]
            splits.append(self._decode_tokens(token_slice))
            start += self.chunk_size - self.chunk_overlap

        chunks = self._make_chunks_from_splits(splits, text)
        return self._build_result(chunks, text, "token")


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

STRATEGIES = {
    "fixed":     FixedSizeChunker,
    "sentence":  SentenceChunker,
    "recursive": RecursiveChunker,
    "token":     TokenChunker,
}


def get_chunker(
    strategy: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    source: str = "",
) -> BaseChunker:
    """
    Factory function — returns the right chunker for the given strategy name.

    Usage:
        chunker = get_chunker("recursive", chunk_size=512, chunk_overlap=50)
        result = chunker.chunk(text)
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy '{strategy}'. "
            f"Choose from: {', '.join(STRATEGIES.keys())}"
        )
    return STRATEGIES[strategy](
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source=source,
    )
