"""Unit tests for the evidence extraction module."""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.evidence.extractor import EvidenceExtractor


class TestEvidenceExtractor:
    """Test cases for EvidenceExtractor class."""
    
    @pytest.fixture
    def extractor(self):
        """Create an EvidenceExtractor instance for testing."""
        return EvidenceExtractor()
    
    # =========================================================================
    # Tests for split_into_sentences()
    # =========================================================================
    
    def test_split_into_sentences_basic(self, extractor):
        """Test basic sentence splitting."""
        text = "This is the first sentence. This is the second sentence. And here is the third."
        sentences = extractor.split_into_sentences(text)
        
        assert len(sentences) == 3
        assert "first sentence" in sentences[0]
        assert "second sentence" in sentences[1]
        assert "third" in sentences[2]
    
    def test_split_into_sentences_scientific(self, extractor):
        """Test sentence splitting with scientific text."""
        text = """Deep learning is a subset of machine learning. 
        It uses neural networks with multiple layers. 
        These networks can learn complex patterns from data."""
        sentences = extractor.split_into_sentences(text)
        
        assert len(sentences) == 3
        assert "deep learning" in sentences[0].lower()
        assert "neural networks" in sentences[1].lower()
    
    def test_split_into_sentences_empty(self, extractor):
        """Test with empty string."""
        sentences = extractor.split_into_sentences("")
        assert sentences == []
    
    def test_split_into_sentences_none(self, extractor):
        """Test with None input."""
        sentences = extractor.split_into_sentences(None)
        assert sentences == []
    
    def test_split_into_sentences_whitespace(self, extractor):
        """Test with whitespace only."""
        sentences = extractor.split_into_sentences("   \n\t  ")
        assert sentences == []
    
    def test_split_into_sentences_filters_short(self, extractor):
        """Test that very short sentences are filtered out."""
        text = "OK. This is a longer sentence that should be kept. Yes."
        sentences = extractor.split_into_sentences(text)
        
        # "OK." and "Yes." should be filtered (< 10 chars)
        assert len(sentences) == 1
        assert "longer sentence" in sentences[0]
    
    def test_split_into_sentences_abbreviations(self, extractor):
        """Test handling of abbreviations like Dr., Mr., etc."""
        text = "Dr. Smith published a paper. The results were significant."
        sentences = extractor.split_into_sentences(text)
        
        # Should handle abbreviations correctly
        assert len(sentences) >= 1

    def test_split_into_sentences_filters_prompt_artifacts(self, extractor):
        """Prompt-like scaffolding such as 'Query:' should be removed as junk."""
        text = (
            "Query: We need to check whether the device has sleep mode and wake-up features. "
            "RAG improves factual grounding by retrieving external evidence."
        )
        sentences = extractor.split_into_sentences(text)

        assert all(not s.lower().startswith("query:") for s in sentences)
        assert any("rag improves factual grounding" in s.lower() for s in sentences)

    def test_query_term_overlap_helper(self, extractor):
        """Keyword overlap helper should require at least one meaningful shared term."""
        assert extractor._has_query_term_overlap(
            "use of rag in ai",
            "RAG improves factual grounding for language models",
            min_overlap=1,
        )
        assert not extractor._has_query_term_overlap(
            "use of rag in ai",
            "Healthcare regulation and bioethics are critical",
            min_overlap=1,
        )
    
    # =========================================================================
    # Tests for compute_sentence_similarity()
    # =========================================================================
    
    def test_compute_sentence_similarity_basic(self, extractor):
        """Test basic similarity computation."""
        query = "What is machine learning?"
        sentences = [
            "Machine learning is a type of artificial intelligence.",
            "The weather is nice today.",
            "Deep learning uses neural networks."
        ]
        
        similarities = extractor.compute_sentence_similarity(query, sentences)
        
        assert len(similarities) == 3
        # First sentence should be most similar (contains "machine learning")
        assert similarities[0][0] == sentences[0] or "machine learning" in similarities[0][0].lower()
        # All scores should be between -1 and 1 (cosine similarity)
        for _, score in similarities:
            assert -1 <= score <= 1
    
    def test_compute_sentence_similarity_empty(self, extractor):
        """Test with empty sentence list."""
        similarities = extractor.compute_sentence_similarity("query", [])
        assert similarities == []
    
    def test_compute_sentence_similarity_sorted(self, extractor):
        """Test that results are sorted by score descending."""
        query = "neural networks"
        sentences = [
            "The cat sat on the mat.",
            "Neural networks are used in deep learning.",
            "Weather forecast for tomorrow."
        ]
        
        similarities = extractor.compute_sentence_similarity(query, sentences)
        
        # Should be sorted descending by score
        scores = [s[1] for s in similarities]
        assert scores == sorted(scores, reverse=True)
    
    # =========================================================================
    # Tests for select_best_sentence()
    # =========================================================================
    
    def test_select_best_sentence_basic(self, extractor):
        """Test selecting the best sentence from text."""
        query = "What is deep learning?"
        text = """Deep learning is a subset of machine learning. 
        It involves training neural networks. 
        The weather is nice today."""
        
        result = extractor.select_best_sentence(query, text)
        
        assert "best_sentence" in result
        assert "best_score" in result
        assert "all_sentences" in result
        assert result["best_score"] > 0
    
    def test_select_best_sentence_empty_text(self, extractor):
        """Test with empty text."""
        result = extractor.select_best_sentence("query", "")
        
        assert result["best_sentence"] == ""
        assert result["best_score"] == 0.0
    
    def test_select_best_sentence_below_threshold(self, extractor):
        """Test when best sentence is below threshold."""
        query = "quantum computing algorithms"
        text = "The cat sat on the mat. Dogs are friendly animals."
        
        result = extractor.select_best_sentence(query, text, min_similarity=0.9)
        
        assert "below_threshold" in result
        # With very different topics and high threshold, should be below
    
    # =========================================================================
    # Tests for extract_evidence_from_chunks()
    # =========================================================================
    
    def test_extract_evidence_from_chunks_basic(self, extractor):
        """Test evidence extraction from chunks."""
        query = "What is deep learning?"
        chunks = [
            {
                "chunk_id": "1",
                "text": "Deep learning uses neural networks. It is very powerful.",
                "paper_title": "Test Paper",
                "paper_year": 2023,
                "similarity_score": 0.8
            }
        ]
        
        enhanced = extractor.extract_evidence_from_chunks(query, chunks)
        
        assert len(enhanced) == 1
        assert "evidence_sentence" in enhanced[0]
        assert "evidence_score" in enhanced[0]
        assert enhanced[0]["chunk_id"] == "1"  # Original data preserved
    
    def test_extract_evidence_from_chunks_empty(self, extractor):
        """Test with empty chunks list."""
        enhanced = extractor.extract_evidence_from_chunks("query", [])
        assert enhanced == []
    
    def test_extract_evidence_from_chunks_preserves_data(self, extractor):
        """Test that original chunk data is preserved."""
        query = "test"
        chunks = [
            {
                "chunk_id": "abc123",
                "text": "This is a test sentence. Another test here.",
                "paper_title": "Original Title",
                "paper_year": 2024,
                "similarity_score": 0.75,
                "custom_field": "preserved"
            }
        ]
        
        enhanced = extractor.extract_evidence_from_chunks(query, chunks)
        
        assert enhanced[0]["chunk_id"] == "abc123"
        assert enhanced[0]["paper_title"] == "Original Title"
        assert enhanced[0]["custom_field"] == "preserved"
    
    def test_extract_evidence_top_n_sentences(self, extractor):
        """Test extracting top N sentences."""
        query = "machine learning"
        chunks = [
            {
                "chunk_id": "1",
                "text": "Machine learning is powerful. Deep learning is a subset. Neural networks are used.",
                "paper_title": "ML Paper",
                "paper_year": 2023
            }
        ]
        
        enhanced = extractor.extract_evidence_from_chunks(query, chunks, top_n_sentences=2)
        
        assert len(enhanced) == 1
        if "top_sentences" in enhanced[0]:
            assert len(enhanced[0]["top_sentences"]) <= 2
    
    # =========================================================================
    # Tests for format_evidence_output()
    # =========================================================================
    
    def test_format_evidence_output_basic(self, extractor):
        """Test formatting evidence output."""
        enhanced_chunks = [
            {
                "paper_title": "Test Paper",
                "paper_year": 2023,
                "similarity_score": 0.85,
                "evidence_sentence": "This is the key evidence.",
                "evidence_score": 0.92,
                "evidence_below_threshold": False
            }
        ]
        
        output = extractor.format_evidence_output(enhanced_chunks)
        
        assert "SENTENCE-LEVEL EVIDENCE" in output
        assert "Test Paper" in output
        assert "2023" in output
        assert "0.85" in output or "0.8500" in output
        assert "0.92" in output or "0.9200" in output
        assert "key evidence" in output
    
    def test_format_evidence_output_below_threshold(self, extractor):
        """Test formatting when evidence is below threshold."""
        enhanced_chunks = [
            {
                "paper_title": "Test Paper",
                "paper_year": 2023,
                "similarity_score": 0.5,
                "evidence_sentence": "Some text.",
                "evidence_score": 0.2,
                "evidence_below_threshold": True
            }
        ]
        
        output = extractor.format_evidence_output(enhanced_chunks)
        
        assert "Below similarity threshold" in output or "⚠" in output
    
    def test_format_evidence_output_empty(self, extractor):
        """Test formatting with empty chunks."""
        output = extractor.format_evidence_output([])
        
        assert "SENTENCE-LEVEL EVIDENCE" in output


class TestEvidenceExtractorIntegration:
    """Integration tests for EvidenceExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create an EvidenceExtractor instance."""
        return EvidenceExtractor()
    
    def test_full_pipeline(self, extractor):
        """Test the full evidence extraction pipeline."""
        query = "How do neural networks learn?"
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": """Neural networks learn through backpropagation. 
                The algorithm adjusts weights based on errors. 
                This process is repeated many times during training.""",
                "paper_title": "Neural Network Fundamentals",
                "paper_year": 2022,
                "similarity_score": 0.78
            },
            {
                "chunk_id": "chunk_2", 
                "text": """Deep learning models require large datasets.
                The training process can take hours or days.
                GPUs are commonly used to speed up training.""",
                "paper_title": "Deep Learning Training",
                "paper_year": 2023,
                "similarity_score": 0.65
            }
        ]
        
        # Extract evidence
        enhanced = extractor.extract_evidence_from_chunks(query, chunks)
        
        # Verify structure
        assert len(enhanced) == 2
        for chunk in enhanced:
            assert "evidence_sentence" in chunk
            assert "evidence_score" in chunk
            assert isinstance(chunk["evidence_score"], float)
        
        # Format output
        output = extractor.format_evidence_output(enhanced)
        assert "Neural Network Fundamentals" in output
        assert "Deep Learning Training" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
