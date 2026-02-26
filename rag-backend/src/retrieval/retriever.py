"""Retrieval logic for semantic search and chunk retrieval."""

import numpy as np
from typing import List, Dict, Any, Tuple
from src.embeddings.embedder import EmbeddingGenerator
from src.vector_store import FAISSVectorStore
from src.database import get_mongo_client
from src.config import Config


class Retriever:
    """Retrieve relevant chunks based on query."""
    
    def __init__(self):
        self.embedder = EmbeddingGenerator()
        self.vector_store = FAISSVectorStore()
        self.mongo = get_mongo_client()
    
    def retrieve_chunks(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User query string
            top_k: Number of top chunks to retrieve
            
        Returns:
            List of chunk objects with metadata and similarity scores
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
            return results
        
        except Exception as e:
            print(f"✗ Error retrieving chunks: {e}")
            return []
    
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
