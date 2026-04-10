# FILE: src/embeddings/embedder.py
"""Embedding generation using SciBERT with an MD5-keyed LRU Cache."""

import hashlib
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from src.config import Config


class BaseEmbedder:
    """Raw SentenceTransformer wrapper."""
    def __init__(self):
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL)

    def encode(self, texts: List[str], normalize_embeddings: bool = True, batch_size: int = 32) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=normalize_embeddings, batch_size=batch_size, show_progress_bar=False)


class CachedEmbedder:
    """LRU Cache wrapper around the base embedder."""
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_cache_size: int = 2048):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._embedder = BaseEmbedder()
        self._cache: Dict[str, np.ndarray] = {}
        self._max_size = max_cache_size
        self._initialized = True
        print(f"✓ Loaded CachedEmbedder with model: {Config.EMBEDDING_MODEL}")

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        Returns Normalized embedding vector
        """
        key = hashlib.md5(text.encode()).hexdigest()
        if key not in self._cache:
            if len(self._cache) >= self._max_size:
                # Evict oldest 10%
                evict = list(self._cache.keys())[:self._max_size // 10]
                for k in evict: del self._cache[k]
            self._cache[key] = self._embedder.encode([text], normalize_embeddings=True)[0]
        return self._cache[key]

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts.
        Only encode cache misses, fill hits from cache.
        """
        misses = [t for t in texts if hashlib.md5(t.encode()).hexdigest() not in self._cache]
        if misses:
            vectors = self._embedder.encode(misses, normalize_embeddings=True, batch_size=32)
            for t, v in zip(misses, vectors):
                self._cache[hashlib.md5(t.encode()).hexdigest()] = v
        return [self._cache[hashlib.md5(t.encode()).hexdigest()] for t in texts]

    def generate_chunk_embeddings(self, chunks: List[Dict[str, Any]]) -> tuple[List[np.ndarray], List[Dict[str, Any]]]:
        """
        Generate embeddings for chunks (legacy signature support).
        Returns a tuple of (embeddings, chunks) to match previous usage.
        """
        texts = [chunk.get("text", "") for chunk in chunks]
        embeddings = self.embed_batch(texts)
        return embeddings, chunks


def get_shared_embedder() -> CachedEmbedder:
    """Return the global CachedEmbedder singleton."""
    return CachedEmbedder()
