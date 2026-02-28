"""Retrieval logic for semantic search and chunk retrieval."""

import numpy as np
from typing import List, Dict, Any, Tuple
from src.embeddings.embedder import EmbeddingGenerator
from src.vector_store import FAISSVectorStore
from src.database import get_mongo_client
from src.config import Config


class Retriever:
    """Retrieve relevant chunks based on query."""
    
    def __init__(self, use_evidence: bool = False):
        """
        Initialize retriever.
        
        Args:
            use_evidence: If True, enables Stage 2 sentence-level evidence extraction
        """
        self.embedder = EmbeddingGenerator()
        self.vector_store = FAISSVectorStore()
        self.mongo = get_mongo_client()
        self.use_evidence = use_evidence
        self._evidence_extractor = None
    
    @property
    def evidence_extractor(self):
        """Lazy load evidence extractor only when needed."""
        if self._evidence_extractor is None and self.use_evidence:
            from src.evidence.extractor import EvidenceExtractor
            self._evidence_extractor = EvidenceExtractor()
        return self._evidence_extractor
    
    def retrieve_chunks(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User query string
            top_k: Number of top chunks to retrieve
            
        Returns:
            List of chunk objects with metadata and similarity scores.
            If use_evidence=True, includes sentence-level evidence.
        """
        if top_k is None:
            top_k = Config.TOP_K
        
        try:
            # Embed query
            query_embedding = self.embedder.embed_text(query)
            
            # Search FAISS
            distances, indices = self.vector_store.search(query_embedding, top_k)
            
            # Retrieve chunks from MongoDB
            chunks_collection = self.mongo.get_chunks_collection()
            papers_collection = self.mongo.get_papers_collection()
            
            results = []
            
            for similarity_score, embedding_idx in zip(distances, indices):
                if embedding_idx == -1:  # Invalid index
                    continue
                
                # Find chunk by embedding_index
                chunk = chunks_collection.find_one({"embedding_index": int(embedding_idx)})
                
                if chunk:
                    # Fetch paper metadata
                    paper = papers_collection.find_one({"paper_id": chunk.get("paper_id")})
                    
                    result = {
                        "chunk_id": chunk.get("chunk_id"),
                        "text": chunk.get("text"),
                        "paper_id": chunk.get("paper_id"),
                        "paper_title": paper.get("title", "Unknown") if paper else "Unknown",
                        "paper_year": paper.get("year", "N/A") if paper else "N/A",
                        "similarity_score": float(similarity_score),
                        "section": chunk.get("section", "abstract")
                    }
                    results.append(result)
            
            print(f"✓ Retrieved {len(results)} relevant chunks")
            
            # Stage 2: Extract sentence-level evidence if enabled
            if self.use_evidence and results:
                results = self._extract_evidence(query, results)
            
            return results
        
        except Exception as e:
            print(f"✗ Error retrieving chunks: {e}")
            return []
    
    def _extract_evidence(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract sentence-level evidence from chunks (Stage 2).
        
        Args:
            query: The user query
            chunks: Retrieved chunks
            
        Returns:
            Chunks enhanced with evidence_sentence and evidence_score
        """
        if not self.evidence_extractor:
            return chunks
        
        print(f"🔍 Extracting sentence-level evidence...")
        enhanced_chunks = self.evidence_extractor.extract_evidence_from_chunks(query, chunks)
        print(f"✓ Extracted evidence from {len(enhanced_chunks)} chunks")
        
        return enhanced_chunks
    
    def format_retrieval_results(self, results: List[Dict[str, Any]]) -> str:
        """
        Format retrieval results for display.
        
        Args:
            results: List of retrieved chunks
            
        Returns:
            Formatted string for display
        """
        if not results:
            return "No relevant chunks found."
        
        formatted = "\n" + "="*80 + "\n"
        formatted += "RETRIEVED EVIDENCE\n"
        formatted += "="*80 + "\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"[{i}] {result['paper_title']} ({result['paper_year']})\n"
            formatted += f"    Similarity: {result['similarity_score']:.4f}\n"
            formatted += f"    Text: {result['text'][:150]}...\n\n"
        
        return formatted
    
    def multi_retrieve(
        self, 
        search_queries: List[str], 
        top_k_per_query: int = 5,
        max_total: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks for multiple search queries and merge results.
        
        Stage 3 feature: Given multiple decomposed sub-queries from the planner,
        retrieve relevant chunks for each and return a deduplicated, merged set.
        
        Args:
            search_queries: List of search query strings
            top_k_per_query: Number of chunks to retrieve per query
            max_total: Maximum total chunks to return after merging
            
        Returns:
            Deduplicated list of chunks sorted by best similarity score
        """
        if not search_queries:
            return []
        
        print(f"🔍 Multi-query retrieval for {len(search_queries)} queries...")
        
        # Track chunks by chunk_id for deduplication
        # Store best similarity score for each chunk
        chunks_map: Dict[str, Dict[str, Any]] = {}
        
        for query in search_queries:
            print(f"  → Searching: {query[:60]}...")
            
            try:
                # Embed query
                query_embedding = self.embedder.embed_text(query)
                
                # Search FAISS
                distances, indices = self.vector_store.search(query_embedding, top_k_per_query)
                
                # Retrieve chunks from MongoDB
                chunks_collection = self.mongo.get_chunks_collection()
                papers_collection = self.mongo.get_papers_collection()
                
                for similarity_score, embedding_idx in zip(distances, indices):
                    if embedding_idx == -1:
                        continue
                    
                    chunk = chunks_collection.find_one({"embedding_index": int(embedding_idx)})
                    
                    if chunk:
                        chunk_id = chunk.get("chunk_id")
                        
                        # If we've seen this chunk, keep best score
                        if chunk_id in chunks_map:
                            if similarity_score > chunks_map[chunk_id]["similarity_score"]:
                                chunks_map[chunk_id]["similarity_score"] = float(similarity_score)
                            continue
                        
                        # Fetch paper metadata
                        paper = papers_collection.find_one({"paper_id": chunk.get("paper_id")})
                        
                        result = {
                            "chunk_id": chunk_id,
                            "text": chunk.get("text"),
                            "paper_id": chunk.get("paper_id"),
                            "paper_title": paper.get("title", "Unknown") if paper else "Unknown",
                            "paper_year": paper.get("year", "N/A") if paper else "N/A",
                            "similarity_score": float(similarity_score),
                            "section": chunk.get("section", "abstract"),
                            "matched_query": query  # Track which query matched
                        }
                        chunks_map[chunk_id] = result
                        
            except Exception as e:
                print(f"  ⚠ Error searching for query '{query[:30]}...': {e}")
                continue
        
        # Convert to list and sort by similarity score
        results = list(chunks_map.values())
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # Total pool size before filtering (FAISS index size)
        total_pool = self.vector_store.get_index_size()
        
        # Limit to max_total
        results = results[:max_total]
        
        # Attach total pool size so verification can compute real density
        for r in results:
            r["_total_chunks_searched"] = total_pool
        
        print(f"✓ Multi-retrieve found {len(results)} unique chunks from {len(search_queries)} queries")
        
        # Stage 2: Extract sentence-level evidence if enabled
        if self.use_evidence and results:
            # Use the first query as the main query for evidence extraction
            main_query = search_queries[0] if search_queries else ""
            results = self._extract_evidence(main_query, results)
        
        return results
