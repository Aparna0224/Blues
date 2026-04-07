"""BM25 keyword search index for hybrid retrieval.

Uses rank_bm25.BM25Okapi to provide lexical/keyword-based search
alongside the existing FAISS semantic search. Results are fused
via Reciprocal Rank Fusion (RRF) in hybrid_retriever.py.
"""

from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from src.config import Config


# Common English stopwords for tokenizer
_STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "get", "got", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't",
    "it", "its", "itself", "just", "let", "ll", "me", "might", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "now", "of",
    "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves",
    "out", "over", "own", "re", "s", "same", "shan't", "she", "should",
    "shouldn't", "so", "some", "such", "t", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "ve",
    "very", "was", "wasn't", "we", "were", "weren't", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with",
    "won't", "would", "wouldn't", "you", "your", "yours", "yourself",
    "yourselves",
})


# Singleton instance cache
_bm25_instance: Optional["BM25Index"] = None


class BM25Index:
    """BM25 keyword search index using BM25Okapi.

    Provides lexical search capabilities to complement FAISS semantic search.
    Follows the singleton pattern (cached in memory) matching the FAISS store.

    Usage:
        # From MongoDB (cached mode):
        index = BM25Index()
        index.build_from_mongo()
        results = index.search("keyword query", top_k=20)

        # From in-memory chunks (dynamic mode):
        index = BM25Index()
        index.build_from_chunks(chunk_list)
        results = index.search("keyword query", top_k=20)
    """

    def __init__(self):
        """Initialize BM25Index with empty state."""
        self._bm25: Optional[BM25Okapi] = None
        self._chunks: List[Dict[str, Any]] = []
        self._tokenized_corpus: List[List[str]] = []
        self._is_built = False

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text by lowercasing, splitting, and removing stopwords.

        Args:
            text: Input text string to tokenize.

        Returns:
            List of cleaned, lowercased tokens with stopwords removed.
        """
        if not text:
            return []
        tokens = []
        for word in text.lower().split():
            # Strip punctuation
            cleaned = word.strip(".,;:!?()[]{}\"'`-–—/\\|@#$%^&*+=~<>")
            if cleaned and cleaned not in _STOP_WORDS and len(cleaned) > 1:
                tokens.append(cleaned)
        return tokens

    def build_from_mongo(self, force_rebuild: bool = False) -> None:
        """Load all chunks from MongoDB and build the BM25 index.

        Uses a singleton pattern: if already built, returns immediately
        unless force_rebuild is True.

        Args:
            force_rebuild: If True, rebuild even if index already exists.
        """
        if self._is_built and not force_rebuild:
            return

        try:
            from src.database import get_mongo_client

            mongo = get_mongo_client()
            mongo.connect()
            chunks_collection = mongo.get_chunks_collection()
            papers_collection = mongo.get_papers_collection()

            raw_chunks = list(chunks_collection.find({}))

            if not raw_chunks:
                print("⚠ BM25: No chunks found in MongoDB — index is empty")
                self._bm25 = None
                self._chunks = []
                self._tokenized_corpus = []
                self._is_built = True
                return

            # Fetch all papers once to avoid N+1 query overhead
            all_papers = list(papers_collection.find({}))
            papers_lookup = {p.get("paper_id"): p for p in all_papers if p.get("paper_id")}

            # Build chunk dicts with paper metadata
            chunks = []
            for chunk in raw_chunks:
                paper = papers_lookup.get(chunk.get("paper_id"))
                metadata = chunk.get("metadata") or {}
                if not metadata and paper:
                    metadata = {
                        "title": paper.get("title", ""),
                        "year": paper.get("year", ""),
                        "section": chunk.get("section", "abstract"),
                        "summary": "",
                        "tags": [],
                        "category": "general",
                        "source": paper.get("source", ""),
                    }
                chunks.append({
                    "chunk_id": chunk.get("chunk_id"),
                    "text": chunk.get("text", ""),
                    "paper_id": chunk.get("paper_id"),
                    "paper_title": (
                        paper.get("title", "Unknown") if paper else "Unknown"
                    ),
                    "paper_year": (
                        paper.get("year", "N/A") if paper else "N/A"
                    ),
                    "section": chunk.get("section", "abstract"),
                    "metadata": metadata,
                })

            self._build_index(chunks)
            print(f"✓ BM25 index built from MongoDB: {len(chunks)} chunks")

        except Exception as e:
            print(f"⚠ BM25 build_from_mongo failed: {e}")
            self._bm25 = None
            self._chunks = []
            self._tokenized_corpus = []
            self._is_built = True

    def build_from_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Build the BM25 index from an in-memory list of chunk dicts.

        Used by DynamicRetriever for on-the-fly BM25 scoring without
        requiring MongoDB.

        Args:
            chunks: List of chunk dicts, each must have at least 'text'
                    and 'chunk_id' keys.
        """
        if not chunks:
            self._bm25 = None
            self._chunks = []
            self._tokenized_corpus = []
            self._is_built = True
            return

        self._build_index(chunks)
        print(f"✓ BM25 index built from {len(chunks)} in-memory chunks")

    def _build_index(self, chunks: List[Dict[str, Any]]) -> None:
        """Internal: tokenize corpus and construct BM25Okapi model.

        If a chunk has ``paper_facts`` (populated by Phase 2 extract_paper_facts),
        the fact tokens are repeated FACTS_BOOST_FACTOR times to increase recall
        for comparison-focused queries.

        Args:
            chunks: List of chunk dicts to index.
        """
        FACTS_BOOST_FACTOR = 3

        self._chunks = list(chunks)
        tokenized: List[List[str]] = []

        for c in self._chunks:
            tokens = self._tokenize(c.get("text", ""))

            # Boost paper_facts tokens if present
            facts = c.get("paper_facts")
            if isinstance(facts, dict):
                boost_text_parts: List[str] = []
                for key in ("datasets", "model_names", "metrics"):
                    for val in (facts.get(key) or []):
                        boost_text_parts.append(str(val).lower())
                if boost_text_parts:
                    boost_tokens = self._tokenize(" ".join(boost_text_parts))
                    tokens.extend(boost_tokens * FACTS_BOOST_FACTOR)

            tokenized.append(tokens)

        self._tokenized_corpus = tokenized
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        self._is_built = True

    def search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """Search the BM25 index and return ranked chunk dicts.

        Args:
            query: Search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of chunk dicts sorted by BM25 score descending,
            each with an added 'bm25_score' field.
        """
        if not self._is_built or self._bm25 is None or not self._chunks:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k indices sorted by score descending
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        results = []
        for idx in ranked_indices:
            if scores[idx] <= 0:
                continue
            chunk = dict(self._chunks[idx])  # copy
            chunk["bm25_score"] = float(scores[idx])
            results.append(chunk)

        return results


def get_bm25_index(force_rebuild: bool = False) -> BM25Index:
    """Get or create the singleton BM25Index instance.

    Mirrors the FAISS store singleton pattern for consistency.

    Args:
        force_rebuild: If True, rebuild the index from MongoDB.

    Returns:
        The shared BM25Index instance.
    """
    global _bm25_instance
    if _bm25_instance is None:
        _bm25_instance = BM25Index()
    if force_rebuild:
        _bm25_instance.build_from_mongo(force_rebuild=True)
    return _bm25_instance
