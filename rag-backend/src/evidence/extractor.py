"""Evidence extractor for sentence-level similarity scoring.

This module implements Stage 2 of the RAG pipeline:
- Splits chunk text into sentences using NLTK
- Computes sentence-level embeddings using SciBERT
- Selects the best matching sentence for each chunk
- Returns structured evidence with similarity scores
"""

import nltk
from typing import List, Dict, Any, Tuple
import numpy as np
from src.embeddings.embedder import EmbeddingGenerator


class EvidenceExtractor:
    """Extract sentence-level evidence from retrieved chunks."""
    
    def __init__(self):
        """Initialize evidence extractor with NLTK sentence tokenizer."""
        # Download NLTK data if not present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            print("📥 Downloading NLTK punkt tokenizer...")
            nltk.download('punkt', quiet=True)
        
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            print("📥 Downloading NLTK punkt_tab tokenizer...")
            nltk.download('punkt_tab', quiet=True)
        
        self.embedder = EmbeddingGenerator()
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using NLTK.
        
        Args:
            text: Input text to split
            
        Returns:
            List of sentences
        """
        if not text or not text.strip():
            return []
        
        sentences = nltk.sent_tokenize(text)
        # Filter out very short sentences (likely noise)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        return sentences
    
    def compute_sentence_similarity(
        self, 
        query: str, 
        sentences: List[str]
    ) -> List[Tuple[str, float]]:
        """
        Compute similarity between query and each sentence.
        
        Args:
            query: The query string
            sentences: List of sentences to compare
            
        Returns:
            List of (sentence, similarity_score) tuples sorted by score descending
        """
        if not sentences:
            return []
        
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)
        
        # Generate sentence embeddings
        sentence_embeddings = self.embedder.embed_batch(sentences)
        
        # Compute cosine similarities (embeddings are already normalized)
        similarities = []
        for i, sentence in enumerate(sentences):
            # Cosine similarity via dot product (normalized vectors)
            similarity = float(np.dot(query_embedding, sentence_embeddings[i]))
            similarities.append((sentence, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities
    
    def select_best_sentence(
        self, 
        query: str, 
        text: str, 
        min_similarity: float = 0.3
    ) -> Dict[str, Any]:
        """
        Select the most relevant sentence from text for a given query.
        
        Args:
            query: The query string
            text: The chunk text to analyze
            min_similarity: Minimum similarity threshold
            
        Returns:
            Dictionary with best sentence, score, and all sentence scores
        """
        sentences = self.split_into_sentences(text)
        
        if not sentences:
            return {
                "best_sentence": text[:200] if text else "",
                "best_score": 0.0,
                "all_sentences": []
            }
        
        similarities = self.compute_sentence_similarity(query, sentences)
        
        if not similarities:
            return {
                "best_sentence": sentences[0] if sentences else "",
                "best_score": 0.0,
                "all_sentences": []
            }
        
        best_sentence, best_score = similarities[0]
        
        # If best score is below threshold, return empty
        if best_score < min_similarity:
            return {
                "best_sentence": best_sentence,
                "best_score": best_score,
                "all_sentences": similarities,
                "below_threshold": True
            }
        
        return {
            "best_sentence": best_sentence,
            "best_score": best_score,
            "all_sentences": similarities,
            "below_threshold": False
        }
    
    def extract_evidence_from_chunks(
        self, 
        query: str, 
        chunks: List[Dict[str, Any]],
        top_n_sentences: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Extract sentence-level evidence from retrieved chunks.
        
        This is the main method for Stage 2 evidence extraction.
        For each chunk, it finds the most relevant sentence(s) to the query.
        
        Args:
            query: The query string
            chunks: List of retrieved chunk objects
            top_n_sentences: Number of top sentences to return per chunk
            
        Returns:
            List of chunks enhanced with evidence information:
            - evidence_sentence: The most relevant sentence
            - evidence_score: Similarity score for the evidence
            - sentence_scores: All sentence scores for the chunk
        """
        enhanced_chunks = []
        
        for chunk in chunks:
            text = chunk.get("text", "")
            
            # Extract evidence for this chunk
            evidence = self.select_best_sentence(query, text)
            
            # Create enhanced chunk with evidence
            enhanced_chunk = {
                **chunk,
                "evidence_sentence": evidence["best_sentence"],
                "evidence_score": evidence["best_score"],
                "evidence_below_threshold": evidence.get("below_threshold", False),
            }
            
            # Add top N sentences if requested
            if top_n_sentences > 1 and evidence.get("all_sentences"):
                enhanced_chunk["top_sentences"] = [
                    {"sentence": s, "score": sc} 
                    for s, sc in evidence["all_sentences"][:top_n_sentences]
                ]
            
            enhanced_chunks.append(enhanced_chunk)
        
        return enhanced_chunks
    
    def format_evidence_output(self, enhanced_chunks: List[Dict[str, Any]]) -> str:
        """
        Format enhanced chunks as human-readable evidence output.
        
        Args:
            enhanced_chunks: Chunks with evidence information
            
        Returns:
            Formatted string for display
        """
        output = []
        output.append("=" * 78)
        output.append("SENTENCE-LEVEL EVIDENCE")
        output.append("=" * 78)
        
        for i, chunk in enumerate(enhanced_chunks, 1):
            # Handle both field naming conventions
            title = chunk.get("paper_title", chunk.get("title", "Unknown"))
            year = chunk.get("paper_year", chunk.get("year", "N/A"))
            chunk_sim = chunk.get("similarity_score", chunk.get("similarity", 0))
            evidence_sentence = chunk.get("evidence_sentence", "")
            evidence_score = chunk.get("evidence_score", 0)
            below_threshold = chunk.get("evidence_below_threshold", False)
            
            output.append(f"\n[{i}] {title} ({year})")
            output.append(f"    Chunk Similarity: {chunk_sim:.4f}")
            output.append(f"    Evidence Score: {evidence_score:.4f}")
            if below_threshold:
                output.append(f"    ⚠ Below similarity threshold")
            output.append(f"    Evidence: \"{evidence_sentence[:150]}...\"" 
                         if len(evidence_sentence) > 150 
                         else f"    Evidence: \"{evidence_sentence}\"")
        
        output.append("")
        return "\n".join(output)
