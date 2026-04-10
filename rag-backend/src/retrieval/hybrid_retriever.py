"""Hybrid Retriever Base Implementation."""
import asyncio
from typing import List, Dict, Any
from src.retrieval.bm25_index import get_bm25_index
from src.vector_store import FAISSVectorStore
from src.embeddings.embedder import get_shared_embedder
from src.database import get_mongo_client

class HybridRetrieverBase:
    """Performs Step 1 (FAISS) and Step 2 (BM25) base retrievals per query."""
    
    def __init__(self):
        self.bm25_index = get_bm25_index()
        self.faiss_store = FAISSVectorStore()
        self.embedder = get_shared_embedder()
        self.mongo = get_mongo_client()
        
        if not self.bm25_index._is_built:
            self.bm25_index.build_from_mongo()

    def semantic_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Semantic search via FAISS and MongoDB embedding_index map."""
        embedding = self.embedder.embed_text(query)
        if embedding is None:
            return []
            
        distances, indices = self.faiss_store.search(embedding, top_k=top_k)
        if len(indices) == 0:
            return []
            
        idx_list = indices.tolist()
        distances_list = distances.tolist()
        
        chunks_col = self.mongo.get_chunks_collection()
        docs = list(chunks_col.find({"embedding_index": {"$in": idx_list}}))
        
        results = []
        for doc in docs:
            idx = doc.get("embedding_index")
            if idx in idx_list:
                pos = idx_list.index(idx)
                sim = float(distances_list[pos])
                doc["similarity_score"] = sim
                doc.pop("_id", None)
                results.append(doc)
                
        results.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        return results
            
    async def retrieve_per_query(self, query: str, top_k: int = 20) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Executes parallel semantic and BM25 retrievals for a given query.
        Returns semantic results and BM25 results as separate lists.
        """
        bm25_results = await asyncio.to_thread(self.bm25_index.search, query, top_k)
        semantic_results = await asyncio.to_thread(self.semantic_search, query, top_k)

        
        # Inject matched query to identify them later
        for chunk in bm25_results:
            chunk['matched_query'] = query
        for chunk in semantic_results:
            chunk['matched_query'] = query
            
        return semantic_results, bm25_results
