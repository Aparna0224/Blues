"""FAISS vector store management."""

import os
import numpy as np
import faiss
from typing import List, Tuple, Dict, Any
from src.config import Config


class FAISSVectorStore:
    """Manage FAISS index for semantic search."""
    
    def __init__(self):
        self.index = None
        self.dimension = Config.EMBEDDING_DIMENSION
        self.index_path = Config.FAISS_INDEX_PATH
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize FAISS index."""
        try:
            if os.path.exists(self.index_path):
                self.load_index()
                print(f"✓ Loaded FAISS index from {self.index_path}")
            else:
                # Create new index with IndexFlatIP (Inner Product for cosine similarity)
                self.index = faiss.IndexFlatIP(self.dimension)
                print(f"✓ Created new FAISS index (IndexFlatIP, dimension={self.dimension})")
        except Exception as e:
            print(f"✗ Error initializing index: {e}")
            self.index = faiss.IndexFlatIP(self.dimension)
    
    def add_embeddings(self, embeddings: np.ndarray, chunk_ids: List[str]) -> List[int]:
        """
        Add embeddings to FAISS index.
        
        Args:
            embeddings: Array of embedding vectors (N x D)
            chunk_ids: List of chunk IDs corresponding to embeddings
            
        Returns:
            List of embedding indices assigned by FAISS
        """
        try:
            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings)
            
            # Ensure embeddings are float32
            embeddings = embeddings.astype(np.float32)
            
            # Get current index size before adding
            start_idx = self.index.ntotal
            
            # Add to index
            self.index.add(embeddings)
            
            # Return indices
            indices = list(range(start_idx, start_idx + len(embeddings)))
            print(f"✓ Added {len(embeddings)} embeddings to FAISS index")
            
            return indices
        
        except Exception as e:
            print(f"✗ Error adding embeddings: {e}")
            return []
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search FAISS index for nearest neighbors.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of top results to return
            
        Returns:
            Tuple of (distances, indices)
        """
        try:
            if not isinstance(query_embedding, np.ndarray):
                query_embedding = np.array(query_embedding)
            
            query_embedding = query_embedding.astype(np.float32).reshape(1, -1)
            distances, indices = self.index.search(query_embedding, top_k)
            
            return distances[0], indices[0]
        
        except Exception as e:
            print(f"✗ Error searching index: {e}")
            return np.array([]), np.array([])
    
    def save_index(self):
        """Save FAISS index to disk."""
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            print(f"✓ Saved FAISS index to {self.index_path}")
        except Exception as e:
            print(f"✗ Error saving index: {e}")
    
    def load_index(self):
        """Load FAISS index from disk."""
        try:
            self.index = faiss.read_index(self.index_path)
            print(f"✓ Loaded FAISS index from {self.index_path}")
        except Exception as e:
            print(f"✗ Error loading index: {e}")
            self.index = faiss.IndexFlatIP(self.dimension)
    
    def get_index_size(self) -> int:
        """Get number of vectors in index."""
        return self.index.ntotal if self.index else 0
