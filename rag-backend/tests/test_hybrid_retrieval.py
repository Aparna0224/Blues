"""Unit tests for hybrid retrieval: BM25 index, RRF fusion, and HybridRetriever.

All tests use mock data — no MongoDB or FAISS dependencies required.
"""

import pytest
from unittest.mock import patch, MagicMock


# ─── Fixtures ────────────────────────────────────────────────────

SAMPLE_CHUNKS = [
    {
        "chunk_id": "chunk_001",
        "text": "Artificial general intelligence (AGI) refers to highly autonomous systems that outperform humans at most economically valuable work.",
        "paper_id": "paper_1",
        "paper_title": "Foundations of AGI",
        "paper_year": "2024",
        "section": "abstract",
        "metadata": {"title": "Foundations of AGI", "year": "2024"},
    },
    {
        "chunk_id": "chunk_002",
        "text": "Retrieval augmented generation combines information retrieval with language model generation to produce grounded answers.",
        "paper_id": "paper_2",
        "paper_title": "RAG Systems",
        "paper_year": "2023",
        "section": "body",
        "metadata": {"title": "RAG Systems", "year": "2023"},
    },
    {
        "chunk_id": "chunk_003",
        "text": "Current challenges in AGI development include alignment problems, reward hacking, and interpretability of deep neural networks.",
        "paper_id": "paper_3",
        "paper_title": "AGI Challenges",
        "paper_year": "2025",
        "section": "body",
        "metadata": {"title": "AGI Challenges", "year": "2025"},
    },
    {
        "chunk_id": "chunk_004",
        "text": "Narrow AI systems excel at specific tasks like image classification and natural language processing but lack general reasoning.",
        "paper_id": "paper_4",
        "paper_title": "Narrow vs General AI",
        "paper_year": "2024",
        "section": "abstract",
        "metadata": {"title": "Narrow vs General AI", "year": "2024"},
    },
    {
        "chunk_id": "chunk_005",
        "text": "BM25 is a probabilistic information retrieval function that ranks documents based on query term frequency and inverse document frequency.",
        "paper_id": "paper_5",
        "paper_title": "Information Retrieval Methods",
        "paper_year": "2022",
        "section": "body",
        "metadata": {"title": "Information Retrieval Methods", "year": "2022"},
    },
]


# ─── BM25Index Tests ─────────────────────────────────────────────


class TestBM25Index:
    """Tests for the BM25Index class."""

    def test_bm25_index_build_and_search(self):
        """Build BM25 index from chunk list and verify ranked output."""
        from src.retrieval.bm25_index import BM25Index

        index = BM25Index()
        index.build_from_chunks(SAMPLE_CHUNKS)

        results = index.search("AGI challenges alignment", top_k=5)

        # Should return results
        assert len(results) > 0

        # Results should have bm25_score field
        for r in results:
            assert "bm25_score" in r
            assert r["bm25_score"] > 0

        # Chunk about AGI challenges should rank highly
        chunk_ids = [r["chunk_id"] for r in results]
        assert "chunk_003" in chunk_ids, (
            "Chunk about AGI challenges should appear in results"
        )

    def test_bm25_index_empty_chunks(self):
        """Build from empty list should not crash."""
        from src.retrieval.bm25_index import BM25Index

        index = BM25Index()
        index.build_from_chunks([])

        results = index.search("any query", top_k=5)
        assert results == []

    def test_bm25_index_empty_query(self):
        """Empty query should return no results."""
        from src.retrieval.bm25_index import BM25Index

        index = BM25Index()
        index.build_from_chunks(SAMPLE_CHUNKS)

        results = index.search("", top_k=5)
        assert results == []

    def test_bm25_index_returns_full_chunk_dicts(self):
        """Returned results should contain all original chunk fields."""
        from src.retrieval.bm25_index import BM25Index

        index = BM25Index()
        index.build_from_chunks(SAMPLE_CHUNKS)

        results = index.search("retrieval augmented generation", top_k=3)
        assert len(results) > 0

        first = results[0]
        assert "chunk_id" in first
        assert "text" in first
        assert "paper_id" in first
        assert "bm25_score" in first

    def test_bm25_search_ranking_order(self):
        """Results should be sorted by bm25_score descending."""
        from src.retrieval.bm25_index import BM25Index

        index = BM25Index()
        index.build_from_chunks(SAMPLE_CHUNKS)

        results = index.search("artificial intelligence systems", top_k=5)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i]["bm25_score"] >= results[i + 1]["bm25_score"]


class TestBM25Tokenizer:
    """Tests for the BM25 tokenizer."""

    def test_bm25_tokenizer_stop_words(self):
        """Assert stopwords are removed and text is lowercased."""
        from src.retrieval.bm25_index import BM25Index

        tokens = BM25Index._tokenize(
            "The quick brown fox jumps over the lazy dog"
        )

        # Should be lowercased
        assert all(t == t.lower() for t in tokens)

        # Common stopwords should be removed
        assert "the" not in tokens
        assert "over" not in tokens

        # Content words should remain
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        assert "jumps" in tokens
        assert "lazy" in tokens
        assert "dog" in tokens

    def test_bm25_tokenizer_punctuation(self):
        """Punctuation should be stripped from tokens."""
        from src.retrieval.bm25_index import BM25Index

        tokens = BM25Index._tokenize(
            "Hello, world! (testing) [brackets] and 'quotes'."
        )

        # No punctuation-only tokens
        for t in tokens:
            assert not all(c in ".,;:!?()[]{}\"'`" for c in t)

    def test_bm25_tokenizer_empty_input(self):
        """Empty string should return empty list."""
        from src.retrieval.bm25_index import BM25Index

        assert BM25Index._tokenize("") == []
        assert BM25Index._tokenize(None) == []

    def test_bm25_tokenizer_single_char_removal(self):
        """Single character tokens should be removed."""
        from src.retrieval.bm25_index import BM25Index

        tokens = BM25Index._tokenize("I am a AI researcher")
        # 'I', 'a' should be removed (single char after lowercasing)
        assert "i" not in tokens
        assert "a" not in tokens


# ─── RRF Fusion Tests ────────────────────────────────────────────


class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion."""

    def _make_chunk(self, chunk_id, **kwargs):
        """Helper to create a chunk dict."""
        return {
            "chunk_id": chunk_id,
            "text": f"Text for {chunk_id}",
            "paper_id": f"paper_{chunk_id}",
            "paper_title": f"Title {chunk_id}",
            **kwargs,
        }

    def test_rrf_fusion_both_lists(self):
        """Chunks in both lists should score higher than single-list chunks."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        bm25_results = [
            self._make_chunk("A"),
            self._make_chunk("B"),
            self._make_chunk("C"),
        ]
        semantic_results = [
            self._make_chunk("B"),
            self._make_chunk("D"),
            self._make_chunk("A"),
        ]

        fused = HybridRetriever._rrf_fuse(bm25_results, semantic_results, k=60)

        # Find scores
        scores = {c["chunk_id"]: c["rrf_score"] for c in fused}

        # Chunks in both lists ('A' and 'B') should have higher scores
        # than chunks in only one list ('C' and 'D')
        assert scores["A"] > scores["C"], "A (in both) should score > C (BM25 only)"
        assert scores["A"] > scores["D"], "A (in both) should score > D (semantic only)"
        assert scores["B"] > scores["C"], "B (in both) should score > C (BM25 only)"
        assert scores["B"] > scores["D"], "B (in both) should score > D (semantic only)"

    def test_rrf_fusion_single_list_only(self):
        """Chunks in only one list should still appear in output."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        bm25_results = [self._make_chunk("A"), self._make_chunk("B")]
        semantic_results = [self._make_chunk("C"), self._make_chunk("D")]

        fused = HybridRetriever._rrf_fuse(bm25_results, semantic_results, k=60)

        chunk_ids = {c["chunk_id"] for c in fused}
        assert "A" in chunk_ids
        assert "B" in chunk_ids
        assert "C" in chunk_ids
        assert "D" in chunk_ids

        # All should have rrf_score > 0
        for c in fused:
            assert c["rrf_score"] > 0

    def test_rrf_fusion_deduplication(self):
        """Same chunk_id should not be duplicated in output."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        bm25_results = [
            self._make_chunk("A"),
            self._make_chunk("B"),
            self._make_chunk("C"),
        ]
        semantic_results = [
            self._make_chunk("A"),
            self._make_chunk("B"),
            self._make_chunk("C"),
        ]

        fused = HybridRetriever._rrf_fuse(bm25_results, semantic_results, k=60)

        chunk_ids = [c["chunk_id"] for c in fused]
        assert len(chunk_ids) == len(set(chunk_ids)), "No duplicates in output"

    def test_rrf_fusion_score_formula(self):
        """Verify the RRF score formula: 1/(k+rank_bm25) + 1/(k+rank_sem)."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        k = 60
        bm25_results = [self._make_chunk("A")]  # rank 1
        semantic_results = [self._make_chunk("A")]  # rank 1

        fused = HybridRetriever._rrf_fuse(bm25_results, semantic_results, k=k)

        expected_score = 1.0 / (k + 1) + 1.0 / (k + 1)
        assert abs(fused[0]["rrf_score"] - expected_score) < 1e-9

    def test_rrf_fusion_empty_lists(self):
        """Both lists empty should return empty output."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        fused = HybridRetriever._rrf_fuse([], [], k=60)
        assert fused == []

    def test_rrf_fusion_one_empty_list(self):
        """One empty list should still produce results from the other."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        bm25_results = [self._make_chunk("A"), self._make_chunk("B")]

        fused = HybridRetriever._rrf_fuse(bm25_results, [], k=60)
        assert len(fused) == 2

        chunk_ids = {c["chunk_id"] for c in fused}
        assert "A" in chunk_ids
        assert "B" in chunk_ids

    def test_rrf_fusion_sorted_descending(self):
        """Output should be sorted by rrf_score descending."""
        from src.retrieval.hybrid_retriever import HybridRetriever

        bm25_results = [
            self._make_chunk("A"),
            self._make_chunk("B"),
            self._make_chunk("C"),
        ]
        semantic_results = [
            self._make_chunk("C"),
            self._make_chunk("A"),
        ]

        fused = HybridRetriever._rrf_fuse(bm25_results, semantic_results, k=60)
        for i in range(len(fused) - 1):
            assert fused[i]["rrf_score"] >= fused[i + 1]["rrf_score"]


# ─── HybridRetriever Integration Test ───────────────────────────


class TestHybridRetrieverIntegration:
    """End-to-end test with mocked semantic + BM25."""

    @patch("src.retrieval.hybrid_retriever.get_bm25_index")
    @patch("src.retrieval.hybrid_retriever.Retriever")
    def test_hybrid_retrieve_returns_results(
        self, MockRetriever, mock_get_bm25
    ):
        """End-to-end hybrid retrieve with mocked dependencies."""
        # Mock BM25 index
        mock_bm25 = MagicMock()
        mock_bm25._is_built = True
        mock_bm25.search.return_value = [
            {
                "chunk_id": "chunk_001",
                "text": "AGI is artificial general intelligence",
                "paper_id": "p1",
                "paper_title": "AGI Paper",
                "bm25_score": 2.5,
            },
            {
                "chunk_id": "chunk_002",
                "text": "Machine learning is a subset of AI",
                "paper_id": "p2",
                "paper_title": "ML Paper",
                "bm25_score": 1.8,
            },
        ]
        mock_get_bm25.return_value = mock_bm25

        # Mock Retriever
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.semantic_retrieve.return_value = [
            {
                "chunk_id": "chunk_001",
                "text": "AGI is artificial general intelligence",
                "paper_id": "p1",
                "paper_title": "AGI Paper",
                "similarity_score": 0.85,
            },
            {
                "chunk_id": "chunk_003",
                "text": "Deep learning advances neural network research",
                "paper_id": "p3",
                "paper_title": "DL Paper",
                "similarity_score": 0.72,
            },
        ]
        MockRetriever.return_value = mock_retriever_instance

        from src.retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(use_evidence=False)
        results = retriever.retrieve("What is AGI?", top_k=5)

        # Should return results from both sources
        assert len(results) > 0

        # chunk_001 is in both lists → should have highest score
        chunk_ids = [r["chunk_id"] for r in results]
        assert "chunk_001" in chunk_ids

        # All should have rrf_score
        for r in results:
            assert "rrf_score" in r

    @patch("src.retrieval.hybrid_retriever.get_bm25_index")
    @patch("src.retrieval.hybrid_retriever.Retriever")
    def test_hybrid_multi_retrieve_deduplicates(
        self, MockRetriever, mock_get_bm25
    ):
        """Multi-retrieve should deduplicate across sub-questions."""
        mock_bm25 = MagicMock()
        mock_bm25._is_built = True
        mock_bm25.search.return_value = [
            {
                "chunk_id": "shared_chunk",
                "text": "Shared content",
                "paper_id": "p1",
                "paper_title": "Paper 1",
                "bm25_score": 2.0,
            },
        ]
        mock_get_bm25.return_value = mock_bm25

        mock_retriever_instance = MagicMock()
        mock_retriever_instance.semantic_retrieve.return_value = [
            {
                "chunk_id": "shared_chunk",
                "text": "Shared content",
                "paper_id": "p1",
                "paper_title": "Paper 1",
                "similarity_score": 0.9,
            },
        ]
        MockRetriever.return_value = mock_retriever_instance

        from src.retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever(use_evidence=False)
        results = retriever.multi_retrieve(
            ["query 1", "query 2"], top_k_per_query=5, max_total=10
        )

        # shared_chunk appears for both queries but should only be in results once
        chunk_ids = [r["chunk_id"] for r in results]
        assert chunk_ids.count("shared_chunk") == 1
