"""Embedding generation using sentence-transformers."""

import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from src.config import Config


class EmbeddingGenerator:
    """Generate embeddings for text chunks using SciBERT.
    
    Uses a class-level singleton so the heavy model is loaded only once.
    Prefer ``get_shared_embedder()`` over ``EmbeddingGenerator()`` to
    guarantee reuse.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL)
        self._initialized = True
        print(f"✓ Loaded embedding model: {Config.EMBEDDING_MODEL}")


    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Normalized embedding vector
        """
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)
            return embedding
        except Exception as e:
            print(f"✗ Error embedding text: {e}")
            return np.zeros(Config.EMBEDDING_DIMENSION)
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            Array of normalized embedding vectors
        """
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
            # Normalize for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms
            return embeddings
        except Exception as e:
            print(f"✗ Error embedding batch: {e}")
            return np.zeros((len(texts), Config.EMBEDDING_DIMENSION))
    
    def generate_chunk_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for chunks.
        
        Args:
            chunks: List of chunk objects with text
            
        Returns:
            List of chunks (modified in-place with embeddings will be stored separately)
        """
        texts = [chunk.get("text", "") for chunk in chunks]
        embeddings = self.embed_batch(texts)
        
        # Return embeddings as separate array for FAISS
        return embeddings, chunks


def get_shared_embedder() -> EmbeddingGenerator:
    """Return the global EmbeddingGenerator singleton."""
    return EmbeddingGenerator()
