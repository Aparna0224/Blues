"""Execution wrapper for parallel hybrid retrieval."""
import asyncio
from typing import List, Dict, Any, Tuple
from src.retrieval.hybrid_retriever import HybridRetrieverBase

class ParallelRetriever:
    """Handles parallel retrieval fan-out."""
    
    def __init__(self):
        self.base = HybridRetrieverBase()
        
    async def run_parallel_retrieval(self, search_queries: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Executes parallel hybrid retrieval across all planner queries.
        Returns un-fused lists: (all_semantic, all_bm25).
        """
        if not search_queries:
            return [], []
            
        print(f"🔍 [RetrieveNode] Parallel retrieving over {len(search_queries)} queries...")
        
        # Parallel gather
        tasks = [self.base.retrieve_per_query(q, top_k=20) for q in search_queries]
        results = await asyncio.gather(*tasks)
        
        all_semantic = []
        all_bm25 = []
        
        for sem, bm in results:
            all_semantic.extend(sem)
            all_bm25.extend(bm)
            
        return all_semantic, all_bm25
