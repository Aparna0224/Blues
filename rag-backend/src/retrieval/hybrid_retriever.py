"""Hybrid Retriever — BM25 + Semantic Search fused via Reciprocal Rank Fusion.

Combines lexical keyword matching (BM25) with dense semantic search (FAISS)
to improve recall for agentic RAG queries where sub-questions may miss
evidence with pure semantic search alone.

RRF formula:
    RRF_score(doc) = 1 / (k + rank_bm25) + 1 / (k + rank_semantic)

where k is a smoothing constant (default 60).
"""

from typing import List, Dict, Any, Optional
import asyncio
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

    # Phase 6: Map query keywords → preferred paper sections for biased scoring
    SECTION_BIAS_MAP: Dict[str, List[str]] = {
        "dataset": ["dataset", "data", "experiment", "material"],
        "benchmark": ["dataset", "experiment", "evaluation"],
        "model": ["method", "approach", "architecture", "model"],
        "architecture": ["method", "approach", "architecture", "model"],
        "methodology": ["method", "approach", "methodology"],
        "algorithm": ["method", "approach", "algorithm"],
        "result": ["result", "experiment", "evaluation", "performance"],
        "accuracy": ["result", "experiment", "evaluation"],
        "performance": ["result", "experiment", "evaluation"],
        "metric": ["result", "experiment", "evaluation"],
    }

    @classmethod
    def _get_section_bias(cls, query: str) -> Optional[List[str]]:
        """Return preferred sections for this query based on keyword matching."""
        q_lower = (query or "").lower()
        for keyword, sections in cls.SECTION_BIAS_MAP.items():
            if keyword in q_lower:
                return sections
        return None

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

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid retrieval for a single query."""
        # Run BM25 search
        bm25_results = await asyncio.to_thread(self.bm25_index.search, query, Config.BM25_TOP_K)

        # Run semantic search
        semantic_results = await asyncio.to_thread(self.semantic_retriever.semantic_retrieve, query, Config.BM25_TOP_K)

        fused = self._rrf_fuse(bm25_results, semantic_results, k=Config.RRF_K)

        if metadata_filters:
            fused = [c for c in fused if Retriever._passes_metadata_filters(metadata_filters, c)]

        fused = self._apply_soft_filtering(query, fused)
        fused = fused[:top_k]

        if self.use_evidence and fused:
            fused = await asyncio.to_thread(self._extract_evidence, query, fused)

        if fused:
            from src.retrieval.paper_facts import extract_paper_facts
            fused = await asyncio.to_thread(extract_paper_facts, fused)

        return fused

    async def _retrieve_single_async(self, query: str, top_k_per_query: int) -> List[Dict[str, Any]]:
        """Retrieve sequentially within one query context but callable concurrently."""
        bm25_results = await asyncio.to_thread(self.bm25_index.search, query, Config.BM25_TOP_K)
        semantic_results = await asyncio.to_thread(self.semantic_retriever.semantic_retrieve, query, Config.BM25_TOP_K)
        
        fused = self._rrf_fuse(bm25_results, semantic_results, k=Config.RRF_K)
        
        for chunk in fused[:top_k_per_query]:
            chunk["matched_query"] = query
        return fused[:top_k_per_query]

    async def multi_retrieve(
        self,
        search_queries: List[str],
        top_k_per_query: int = 5,
        max_total: int = 15,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not search_queries:
            return []

        print(f"🔍 Hybrid multi-query retrieval for {len(search_queries)} queries...")

        # Run all sub-query retrievals concurrently
        chunk_lists = await asyncio.gather(*[
            self._retrieve_single_async(q, top_k_per_query) for q in search_queries
        ])

        chunks_map: Dict[str, Dict[str, Any]] = {}
        for sublist in chunk_lists:
            for chunk in sublist:
                chunk_id = chunk.get("chunk_id")
                if not chunk_id: continue
                if chunk_id in chunks_map:
                    if chunk.get("rrf_score", 0) > chunks_map[chunk_id].get("rrf_score", 0):
                        chunks_map[chunk_id] = chunk
                else:
                    chunks_map[chunk_id] = chunk

        results = sorted(chunks_map.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)

        if metadata_filters:
            results = [c for c in results if Retriever._passes_metadata_filters(metadata_filters, c)]

        results = self._apply_soft_filtering(search_queries[0], results)

        for query in search_queries:
            bias_sections = self._get_section_bias(query)
            if bias_sections:
                for chunk in results:
                    chunk_section = str((chunk.get("metadata") or {}).get("section", chunk.get("section", ""))).lower()
                    if any(bs in chunk_section for bs in bias_sections):
                        chunk["final_score"] = chunk.get("final_score", chunk.get("rrf_score", 0)) * 1.15
                        chunk["section_bias_applied"] = True

        results.sort(key=lambda c: c.get("final_score", c.get("rrf_score", 0)), reverse=True)
        results = results[:max_total]

        print(f"✓ Hybrid multi-retrieve found {len(results)} unique chunks from {len(search_queries)} queries")

        if self.use_evidence and results:
            main_query = search_queries[0] if search_queries else ""
            results = await asyncio.to_thread(self._extract_evidence, main_query, results)

        if results:
            from src.retrieval.paper_facts import extract_paper_facts
            results = await asyncio.to_thread(extract_paper_facts, results)

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

    def _apply_soft_filtering(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Apply soft, penalty-based filtering after fusion.

        This preserves recall by avoiding hard pre-fusion drops and
        improves precision by penalizing weak lexical/domain/semantic matches.
        """
        if not chunks:
            return []

        adjusted: List[Dict[str, Any]] = []
        min_score = float(Config.MIN_SCORE_THRESHOLD)

        for chunk in chunks:
            base_score = float(chunk.get("rrf_score", 0.0) or 0.0)
            score = base_score

            text = chunk.get("text", "")
            semantic_score = float(chunk.get("similarity_score", 0.0) or 0.0)

            keyword_overlap = self._keyword_overlap(query, text)
            if keyword_overlap < int(Config.KEYWORD_MIN_OVERLAP):
                score *= float(Config.SOFT_FILTER_KEYWORD_PENALTY)

            if not self._passes_domain_gate(query, text):
                score *= float(Config.SOFT_FILTER_DOMAIN_PENALTY)

            if semantic_score < float(Config.SOFT_FILTER_LOW_SEMANTIC_THRESHOLD):
                score *= float(Config.SOFT_FILTER_LOW_SEMANTIC_PENALTY)

            chunk["final_score"] = score
            chunk["keyword_overlap"] = keyword_overlap

            if score >= min_score:
                adjusted.append(chunk)

        adjusted.sort(key=lambda c: c.get("final_score", 0.0), reverse=True)
        return adjusted

    @staticmethod
    def _keyword_overlap(query: str, text: str) -> int:
        """Count lexical overlap between query and chunk text."""
        if not query or not text:
            return 0
        stop_words = {
            "what", "how", "why", "when", "where", "which", "is", "are",
            "does", "do", "can", "the", "a", "an", "in", "of", "and",
            "or", "to", "for", "on", "with", "by", "from", "as", "at",
            "about", "into", "be", "this", "that",
        }
        query_terms = {
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in query.split()
            if w and w.lower() not in stop_words and len(w.strip(".,;:()[]{}\"'`).")) > 2
        }
        if not query_terms:
            return 0
        text_terms = {
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in text.split()
            if w and w.lower() not in stop_words and len(w.strip(".,;:()[]{}\"'`).")) > 2
        }
        return len(query_terms.intersection(text_terms))

    @staticmethod
    def _passes_domain_gate(query: str, text: str) -> bool:
        """Check optional domain keyword gate."""
        if not Config.ENABLE_DOMAIN_KEYWORD_GATE or not Config.DOMAIN_KEYWORDS:
            return True

        query_terms = {
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in query.split()
            if w and len(w) > 2
        }
        domain_terms = set(Config.DOMAIN_KEYWORDS)
        if query_terms.isdisjoint(domain_terms):
            return True

        text_terms = {
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in text.split()
            if w and len(w) > 2
        }
        overlap = len(domain_terms.intersection(text_terms))
        return overlap >= Config.DOMAIN_KEYWORD_MIN_OVERLAP

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
