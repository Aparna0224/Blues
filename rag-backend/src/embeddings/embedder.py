"""Embedding generation using sentence-transformers with GPU support & caching."""

import time
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional
from collections import OrderedDict
from sentence_transformers import SentenceTransformer
from src.config import Config


def _detect_device() -> str:
    """Auto-detect the best available device: CUDA > MPS > CPU."""
    import torch

    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"⚡ CUDA GPU detected: {name}")
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print("⚡ Apple MPS GPU detected")
        return "mps"
    print("💻 No GPU detected — using CPU")
    return "cpu"


class EmbeddingGenerator:
    """Generate embeddings for text chunks using SciBERT.

    Optimisations over the naive implementation:
      1. **GPU auto-detect** — uses CUDA / MPS when available
      2. **Configurable batch size** — ``Config.EMBEDDING_BATCH_SIZE``
      3. **LRU embedding cache** — avoids re-embedding identical texts
      4. **Singleton pattern** — ``get_embedder()`` returns a shared instance
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device or Config.EMBEDDING_DEVICE
        if self.device == "auto":
            self.device = _detect_device()

        self.batch_size = Config.EMBEDDING_BATCH_SIZE

        t0 = time.perf_counter()
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL, device=self.device)
        load_ms = (time.perf_counter() - t0) * 1000
        print(
            f"✓ Loaded embedding model: {Config.EMBEDDING_MODEL} "
            f"on {self.device} ({load_ms:.0f} ms)"
        )

        # LRU cache: hash(text) → normalised embedding
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._cache_max = Config.EMBEDDING_CACHE_SIZE

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()

    def _cache_get(self, text: str) -> Optional[np.ndarray]:
        key = self._text_hash(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, text: str, emb: np.ndarray) -> None:
        key = self._text_hash(text)
        self._cache[key] = emb
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    # ── public API ────────────────────────────────────────────────

    def embed_text(self, text: str) -> np.ndarray:
        """Generate a normalised embedding for a single text (cached)."""
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                batch_size=self.batch_size,
            )
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            self._cache_put(text, embedding)
            return embedding
        except Exception as e:
            print(f"✗ Error embedding text: {e}")
            return np.zeros(Config.EMBEDDING_DIMENSION)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate normalised embeddings for a list of texts.

        Texts already in cache are served from memory; only uncached
        texts are sent to the model in a single batched call.
        """
        if not texts:
            return np.zeros((0, Config.EMBEDDING_DIMENSION))

        n = len(texts)
        results = np.empty((n, Config.EMBEDDING_DIMENSION), dtype=np.float32)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, t in enumerate(texts):
            cached = self._cache_get(t)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(t)

        if uncached_texts:
            try:
                t0 = time.perf_counter()
                embeddings = self.model.encode(
                    uncached_texts,
                    convert_to_numpy=True,
                    batch_size=self.batch_size,
                    show_progress_bar=len(uncached_texts) > 50,
                )
                elapsed = time.perf_counter() - t0
                rate = len(uncached_texts) / elapsed if elapsed > 0 else 0
                print(
                    f"   ⚡ Embedded {len(uncached_texts)} texts in "
                    f"{elapsed:.1f}s ({rate:.0f} texts/sec) [{self.device}]"
                )
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                norms[norms == 0] = 1
                embeddings = embeddings / norms

                for j, idx in enumerate(uncached_indices):
                    results[idx] = embeddings[j]
                    self._cache_put(uncached_texts[j], embeddings[j])
            except Exception as e:
                print(f"✗ Error embedding batch: {e}")
                for idx in uncached_indices:
                    results[idx] = np.zeros(Config.EMBEDDING_DIMENSION)

        return results

    def generate_chunk_embeddings(
        self, chunks: List[Dict[str, Any]]
    ) -> tuple[np.ndarray, List[Dict[str, Any]]]:
        """Generate embeddings for chunks (uses batched encoding)."""
        texts = [chunk.get("text", "") for chunk in chunks]
        embeddings = self.embed_batch(texts)
        return embeddings, chunks


# ── Singleton accessor ────────────────────────────────────────────

_singleton: Optional[EmbeddingGenerator] = None


def get_embedder() -> EmbeddingGenerator:
    """Return the shared EmbeddingGenerator instance (lazy-init)."""
    global _singleton
    if _singleton is None:
        _singleton = EmbeddingGenerator()
    return _singleton
