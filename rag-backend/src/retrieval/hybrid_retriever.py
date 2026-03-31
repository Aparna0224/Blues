"""Hybrid Retriever — BM25 + Semantic Search fused via Reciprocal Rank Fusion.

Combines lexical keyword matching (BM25) with dense semantic search (FAISS)
to improve recall for agentic RAG queries where sub-questions may miss
evidence with pure semantic search alone.

RRF formula:
    RRF_score(doc) = 1 / (k + rank_bm25) + 1 / (k + rank_semantic)

where k is a smoothing constant (default 60).
"""

from typing import List, Dict, Any, Optional
from src.config import Config
from src.retrieval.bm25_index import BM25Index, get_bm25_index
from src.retrieval.retriever import Retriever


class HybridRetriever:
    """Hybrid retriever that fuses BM25 and semantic search via RRF.

    For cached mode: uses FAISS (via Retriever.semantic_retrieve) and
    BM25 (via BM25Index.search), then fuses results with _rrf_fuse.

    For multi-query: runs independent hybrid retrieval per sub-question,
    deduplicates across sub-questions by chunk_id (keeping highest score),
    applies metadata filters post-fusion, and evidence extraction last.
    """

    def __init__(self, use_evidence: bool = True):
        """Initialize HybridRetriever.

        Args:
            use_evidence: If True, enables sentence-level evidence extraction
                          after fusion and deduplication.
        """
        self.semantic_retriever = Retriever(use_evidence=False)
        self.bm25_index = get_bm25_index()
        self.use_evidence = use_evidence
        self._evidence_extractor = None

        # Ensure BM25 index is built from MongoDB
        if not self.bm25_index._is_built:
            self.bm25_index.build_from_mongo()

    @property
    def evidence_extractor(self):
        """Lazy load evidence extractor only when needed."""
        if self._evidence_extractor is None and self.use_evidence:
            from src.evidence.extractor import EvidenceExtractor
            self._evidence_extractor = EvidenceExtractor()
        return self._evidence_extractor

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid retrieval for a single query.

        Runs both BM25 and semantic search, fuses via RRF,
        applies metadata filters post-fusion, then evidence extraction.

        Args:
            query: Search query string.
            top_k: Number of top results to return after fusion.
            metadata_filters: Optional filters applied post-fusion.

        Returns:
            List of chunk dicts sorted by fused RRF score descending.
        """
        # Run BM25 search
        bm25_results = self.bm25_index.search(query, top_k=Config.BM25_TOP_K)

        # Run semantic search (FAISS only, no keyword/domain filters)
        semantic_results = self.semantic_retriever.semantic_retrieve(
            query, top_k=Config.BM25_TOP_K
        )

        # Fuse via RRF
        fused = self._rrf_fuse(bm25_results, semantic_results, k=Config.RRF_K)

        # Apply metadata filters post-fusion
        if metadata_filters:
            fused = [
                c for c in fused
                if Retriever._passes_metadata_filters(metadata_filters, c)
            ]

        # Limit to top_k
        fused = fused[:top_k]

        # Evidence extraction last
        if self.use_evidence and fused:
            fused = self._extract_evidence(query, fused)

        return fused

    def multi_retrieve(
        self,
        search_queries: List[str],
        top_k_per_query: int = 5,
        max_total: int = 15,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Hybrid retrieval for multiple sub-questions with independent per-query search.

        For each sub-question:
            1. Run BM25 search independently
            2. Run semantic search independently
            3. Fuse via RRF

        Then:
            4. Deduplicate across sub-questions by chunk_id (keep highest rrf_score)
            5. Apply metadata filters post-fusion
            6. Apply evidence extraction last

        Args:
            search_queries: List of decomposed search queries.
            top_k_per_query: Number of results per sub-question after fusion.
            max_total: Maximum total chunks after deduplication.
            metadata_filters: Optional filters applied post-fusion.

        Returns:
            Deduplicated list of chunk dicts sorted by best RRF score.
        """
        if not search_queries:
            return []

        print(f"🔍 Hybrid multi-query retrieval for {len(search_queries)} queries...")

        # Collect all results, deduplicating by chunk_id across queries
        chunks_map: Dict[str, Dict[str, Any]] = {}

        for query in search_queries:
            print(f"  → Hybrid search: {query[:60]}...")

            # BM25 search
            bm25_results = self.bm25_index.search(
                query, top_k=Config.BM25_TOP_K
            )

            # Semantic search (FAISS only)
            semantic_results = self.semantic_retriever.semantic_retrieve(
                query, top_k=Config.BM25_TOP_K
            )

            # Fuse via RRF
            fused = self._rrf_fuse(
                bm25_results, semantic_results, k=Config.RRF_K
            )

            # Take top_k_per_query from this sub-question
            for chunk in fused[:top_k_per_query]:
                chunk_id = chunk.get("chunk_id")
                if not chunk_id:
                    continue

                # Tag with matched query
                chunk["matched_query"] = query

                # Deduplicate: keep highest rrf_score
                if chunk_id in chunks_map:
                    if chunk.get("rrf_score", 0) > chunks_map[chunk_id].get(
                        "rrf_score", 0
                    ):
                        chunks_map[chunk_id] = chunk
                else:
                    chunks_map[chunk_id] = chunk

        # Convert to sorted list
        results = sorted(
            chunks_map.values(),
            key=lambda x: x.get("rrf_score", 0),
            reverse=True,
        )

        # Apply metadata filters post-fusion
        if metadata_filters:
            results = [
                c for c in results
                if Retriever._passes_metadata_filters(metadata_filters, c)
            ]

        # Limit to max_total
        results = results[:max_total]

        print(
            f"✓ Hybrid multi-retrieve found {len(results)} unique chunks "
            f"from {len(search_queries)} queries"
        )

        # Evidence extraction last
        if self.use_evidence and results:
            main_query = search_queries[0] if search_queries else ""
            results = self._extract_evidence(main_query, results)

        return results

    @staticmethod
    def _rrf_fuse(
        bm25_results: List[Dict[str, Any]],
        semantic_results: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """Fuse BM25 and semantic results using Reciprocal Rank Fusion.

        RRF_score(doc) = 1/(k + rank_bm25) + 1/(k + rank_semantic)

        Chunks appearing in both lists score higher than single-list chunks.
        Deduplicates by chunk_id.

        Args:
            bm25_results: Ranked list from BM25 search.
            semantic_results: Ranked list from semantic search.
            k: RRF smoothing constant (default 60).

        Returns:
            List of chunk dicts sorted by RRF score descending,
            each with an 'rrf_score' field added.
        """
        # Build rank maps (1-indexed ranks)
        bm25_ranks: Dict[str, int] = {}
        bm25_chunks: Dict[str, Dict[str, Any]] = {}
        for rank, chunk in enumerate(bm25_results, start=1):
            cid = chunk.get("chunk_id")
            if cid and cid not in bm25_ranks:
                bm25_ranks[cid] = rank
                bm25_chunks[cid] = chunk

        semantic_ranks: Dict[str, int] = {}
        semantic_chunks: Dict[str, Dict[str, Any]] = {}
        for rank, chunk in enumerate(semantic_results, start=1):
            cid = chunk.get("chunk_id")
            if cid and cid not in semantic_ranks:
                semantic_ranks[cid] = rank
                semantic_chunks[cid] = chunk

        # Compute RRF scores for all unique chunk_ids
        all_chunk_ids = set(bm25_ranks.keys()) | set(semantic_ranks.keys())
        fused: List[Dict[str, Any]] = []

        for cid in all_chunk_ids:
            # Pick the best available chunk dict (prefer semantic for richer metadata)
            chunk = dict(semantic_chunks.get(cid, bm25_chunks.get(cid, {})))

            bm25_score = (
                1.0 / (k + bm25_ranks[cid]) if cid in bm25_ranks else 0.0
            )
            semantic_score = (
                1.0 / (k + semantic_ranks[cid])
                if cid in semantic_ranks
                else 0.0
            )
            rrf_score = bm25_score + semantic_score

            chunk["rrf_score"] = rrf_score
            chunk["_bm25_rank"] = bm25_ranks.get(cid)
            chunk["_semantic_rank"] = semantic_ranks.get(cid)
            fused.append(chunk)

        # Sort descending by RRF score
        fused.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused

    def _extract_evidence(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract sentence-level evidence from chunks (post-fusion).

        Args:
            query: The user query for evidence extraction context.
            chunks: Fused chunks to extract evidence from.

        Returns:
            Chunks enhanced with evidence_sentence and evidence_score.
        """
        if not self.evidence_extractor:
            return chunks

        print("🔍 Extracting sentence-level evidence...")
        enhanced: List[Dict[str, Any]] = []
        for chunk in chunks:
            chunk_query = chunk.get("matched_query") or query
            text = chunk.get("text", "")
            evidence = self.evidence_extractor.select_best_sentence(
                chunk_query, text
            )
            enhanced.append({
                **chunk,
                "evidence_sentence": evidence.get("best_sentence", ""),
                "evidence_score": evidence.get("best_score", 0.0),
                "evidence_below_threshold": evidence.get(
                    "below_threshold", False
                ),
            })

        print(f"✓ Extracted evidence from {len(enhanced)} chunks")
        return enhanced
