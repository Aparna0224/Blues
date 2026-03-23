"""
Unified similarity scoring for chunk retrieval.

Consolidates similarity scoring logic used across multiple modules
to provide a single source of truth for semantic similarity calculation.
"""

from typing import Tuple, List
import numpy as np


class SimilarityScorer:
    """
    Unified interface for calculating semantic similarity scores.
    
    Provides methods for:
    - Computing similarity between chunk and query embeddings
    - Ranking chunks by relevance
    - Filtering by similarity threshold
    """
    
    @staticmethod
    def calculate_scores(
        chunk_embeddings: np.ndarray,
        query_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Calculate similarity scores between chunks and queries.
        
        Uses matrix multiplication (dot product) for cosine similarity
        with pre-normalized embeddings.
        
        Args:
            chunk_embeddings: Array of shape (num_chunks, embedding_dim)
            query_embeddings: Array of shape (num_queries, embedding_dim)
            
        Returns:
            Scores matrix of shape (num_chunks, num_queries)
            Each value is the similarity score between a chunk and query.
        """
        return chunk_embeddings @ query_embeddings.T
    
    @staticmethod
    def get_top_matches(
        chunk_embeddings: np.ndarray,
        query_embeddings: np.ndarray,
        top_k: int
    ) -> Tuple[List[int], np.ndarray]:
        """
        Get top-k most similar chunks for queries.
        
        Finds the best matching chunk for each query, then ranks by score.
        
        Args:
            chunk_embeddings: Array of shape (num_chunks, embedding_dim)
            query_embeddings: Array of shape (num_queries, embedding_dim)
            top_k: Number of top matches to return
            
        Returns:
            Tuple of (top_indices, best_scores)
            - top_indices: List of chunk indices, sorted by relevance
            - best_scores: Corresponding similarity scores
        """
        # Calculate scores
        scores_matrix = SimilarityScorer.calculate_scores(chunk_embeddings, query_embeddings)
        
        # Find best query for each chunk (max across queries)
        best_query_idx = np.argmax(scores_matrix, axis=1)
        best_scores = scores_matrix[np.arange(len(chunk_embeddings)), best_query_idx]
        
        # Sort and get top-k
        top_indices = np.argsort(best_scores)[::-1][:top_k].tolist()
        
        return top_indices, best_scores
    
    @staticmethod
    def filter_by_threshold(
        chunk_embeddings: np.ndarray,
        query_embeddings: np.ndarray,
        threshold: float = 0.0
    ) -> Tuple[List[int], np.ndarray]:
        """
        Filter chunks by similarity threshold.
        
        Args:
            chunk_embeddings: Array of shape (num_chunks, embedding_dim)
            query_embeddings: Array of shape (num_queries, embedding_dim)
            threshold: Minimum similarity score (default: 0.0)
            
        Returns:
            Tuple of (matching_indices, scores)
            - matching_indices: Indices of chunks above threshold
            - scores: Corresponding similarity scores
        """
        # Calculate scores
        scores_matrix = SimilarityScorer.calculate_scores(chunk_embeddings, query_embeddings)
        
        # Find best query for each chunk
        best_query_idx = np.argmax(scores_matrix, axis=1)
        best_scores = scores_matrix[np.arange(len(chunk_embeddings)), best_query_idx]
        
        # Filter by threshold
        matching_indices = np.where(best_scores >= threshold)[0].tolist()
        
        return matching_indices, best_scores
    
    @staticmethod
    def rank_by_relevance(
        chunk_embeddings: np.ndarray,
        query_embeddings: np.ndarray
    ) -> List[Tuple[int, float]]:
        """
        Rank all chunks by relevance to queries.
        
        Args:
            chunk_embeddings: Array of shape (num_chunks, embedding_dim)
            query_embeddings: Array of shape (num_queries, embedding_dim)
            
        Returns:
            List of (chunk_index, score) tuples, sorted by score descending
        """
        # Calculate scores
        scores_matrix = SimilarityScorer.calculate_scores(chunk_embeddings, query_embeddings)
        
        # Find best query for each chunk
        best_query_idx = np.argmax(scores_matrix, axis=1)
        best_scores = scores_matrix[np.arange(len(chunk_embeddings)), best_query_idx]
        
        # Create ranking tuples
        ranking = [(int(idx), float(score)) for idx, score in enumerate(best_scores)]
        
        # Sort by score descending
        ranking.sort(key=lambda x: x[1], reverse=True)
        
        return ranking
