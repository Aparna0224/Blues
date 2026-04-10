"""Global Reranker Node implementation."""
from typing import List, Dict, Any

class GlobalReranker:
    
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
    
    @staticmethod
    def _keyword_overlap(query: str, text: str) -> int:
        if not query or not text: return 0
        stop = {"what", "how", "why", "when", "where", "which", "is", "are", "does", "the", "a", "an", "on", "in", "with", "this", "that"}
        q_terms = {w.strip(".,()").lower() for w in query.split() if w.lower() not in stop and len(w)>2}
        t_terms = {w.strip(".,()").lower() for w in text.split() if w.lower() not in stop and len(w)>2}
        return len(q_terms.intersection(t_terms))

    @staticmethod
    def global_rerank(all_bm25: List[Dict[str, Any]], all_semantic: List[Dict[str, Any]], queries: List[str]) -> List[Dict[str, Any]]:
        """
        Executes Steps 3, 4, 5 globally.
        Merges, deduplicates by chunk_id, applies RRF, soft-filtering, section bias, and slices to 10.
        """
        k = 60
        
        # 1. Generate ranks per chunk instance grouped by query to correctly process sub-queries
        # To strictly do a global merge: we map chunk_id -> best ranks across all queries, 
        # or we just unify the list based on absolute position within the retrieved sets.
        # Since retrieve_per_query returns the sets per query, we'll assume here all_bm25 are all chunks 
        # concatenated together. But we need their ranks. Instead, for RRF, we can calculate RRF per query 
        # inside the retriever block, or globally flatten them. A strictly specified "Recompute final score"
        # means we should do RRF on the aggregate. 
        
        bm25_ranks = {}
        bm25_chunks = {}
        for rank, chunk in enumerate(all_bm25, start=1):
            cid = chunk.get("chunk_id")
            if cid:
                if cid not in bm25_ranks or rank < bm25_ranks[cid]:
                    bm25_ranks[cid] = rank
                    bm25_chunks[cid] = chunk
                    
        semantic_ranks = {}
        semantic_chunks = {}
        for rank, chunk in enumerate(all_semantic, start=1):
            cid = chunk.get("chunk_id")
            if cid:
                if cid not in semantic_ranks or rank < semantic_ranks[cid]:
                    semantic_ranks[cid] = rank
                    semantic_chunks[cid] = chunk

        all_ids = set(bm25_ranks.keys()) | set(semantic_ranks.keys())
        merged = []
        
        # Main Query for keyword scaling
        main_query = queries[0] if queries else ""
        
        for cid in all_ids:
            chunk = dict(semantic_chunks.get(cid, bm25_chunks.get(cid, {})))
            q_matched = chunk.get('matched_query', main_query)
            
            # Step 3: RRF Fusion
            rank_b = bm25_ranks.get(cid, 0)
            score_b = 1.0 / (k + rank_b) if rank_b > 0 else 0.0
            
            rank_s = semantic_ranks.get(cid, 0)
            score_s = 1.0 / (k + rank_s) if rank_s > 0 else 0.0
            
            rrf_score = score_b + score_s
            
            chunk["bm25_rank"] = rank_b
            chunk["semantic_rank"] = rank_s
            chunk["rrf_score"] = rrf_score
            
            # Step 4: Soft Filtering
            text = chunk.get("text", "")
            raw_sim = float(chunk.get("similarity_score", 0.0))
            overlap = GlobalReranker._keyword_overlap(q_matched, text)
            
            final = rrf_score
            if overlap < 2:
                final *= 0.85
            if raw_sim < 0.35:
                final *= 0.70
                
            # Domain mismatch omitted as it requires complex parsing not requested
            
            if final < 0.005:
                continue # Floor drop
                
            # Step 5: Section Bias
            q_lower = q_matched.lower()
            bias_sections = []
            for keyword, sects in GlobalReranker.SECTION_BIAS_MAP.items():
                if keyword in q_lower:
                    bias_sections.extend(sects)
                    
            if bias_sections:
                sec = str((chunk.get("metadata") or {}).get("section", chunk.get("section", ""))).lower()
                if any(bs in sec for bs in bias_sections):
                    final *= 1.15
            
            chunk["final_score"] = final
            merged.append(chunk)
            
        merged.sort(key=lambda x: x["final_score"], reverse=True)
        return merged[:12] # Keep Top 10-12
