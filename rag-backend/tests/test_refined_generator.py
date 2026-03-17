"""Unit tests for RefinedAnswerGenerator."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.generation.refined_generator import RefinedAnswerGenerator
from src.llm.base import BaseLLM


class MockLLM(BaseLLM):
    """Mock LLM for testing."""
    
    def generate(self, prompt: str) -> str:
        """Return mock response with 5-section structure."""
        return """
EXECUTIVE SUMMARY

This research addresses a critical challenge in machine learning: the need for 
model interpretability. Recent studies demonstrate that explainable AI techniques 
significantly improve user trust and regulatory compliance.

─────────────────────────────────────────────────────────────────────────────────
DETAILED ANALYSIS

Several approaches have emerged in recent years. According to recent research, 
SHAP and LIME are among the most widely adopted methods. These techniques 
provide local explanations through perturbation-based approaches. Studies show 
they achieve fidelity scores of 0.85-0.95.

Additional findings indicate that attention-based methods provide inherent 
interpretability without additional computational overhead. Performance metrics 
show accuracy remains competitive with black-box models.

Implementation challenges include computational cost and standardization issues. 
However, successful deployments in healthcare and finance demonstrate practical 
viability.

─────────────────────────────────────────────────────────────────────────────────
METHODOLOGICAL FOUNDATION

The retrieved studies employ multiple validation approaches including user studies, 
automated metrics, and comparative analysis. Study scopes range from image 
classification to natural language processing across multiple model architectures.

Key validation techniques include fidelity measurement and consistency checking. 
Most studies validate using domain expert judgment.

─────────────────────────────────────────────────────────────────────────────────
PRACTICAL IMPLICATIONS

These findings enable responsible AI deployment in regulated domains. Organizations 
can now select interpretability-performance trade-offs suited to their constraints. 
The evidence strongly supports adoption in healthcare and finance sectors.

Limitations exist in real-time systems where computational overhead is prohibitive. 
Confidence in these findings is HIGH based on multiple independent studies.

─────────────────────────────────────────────────────────────────────────────────
GAPS & FUTURE DIRECTIONS

Key unresolved questions include standardized evaluation metrics and scalability 
to large language models. Recommended next steps include developing benchmark 
datasets and investigating computational efficiency improvements.
        """
    
    def is_available(self) -> bool:
        return True


class TestRefinedAnswerGenerator:
    """Test suite for RefinedAnswerGenerator."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        return MockLLM()
    
    @pytest.fixture
    def generator(self, mock_llm):
        """Create generator instance."""
        return RefinedAnswerGenerator(mock_llm)
    
    @pytest.fixture
    def sample_chunks(self):
        """Sample chunks for testing."""
        return [
            {
                "text": """
                This study examines explainable AI techniques. We employ SHAP and LIME for 
                local explanations. Experiments show 89% user trust improvement. The approach 
                is constrained to image classification tasks. Results indicate strong 
                performance on benchmark datasets with 0.92 fidelity scores.
                """,
                "paper_title": "Explainable AI Methods",
                "paper_year": 2024,
                "section": "methodology",
                "similarity_score": 0.92,
                "paper_id": "paper1",
                "evidence_sentence": "SHAP provides state-of-the-art explanations",
                "evidence_score": 0.88
            },
            {
                "text": """
                Results demonstrate that attention mechanisms provide interpretability. 
                Accuracy: 94%, Precision: 0.93, Recall: 0.91. The method achieves 
                computational efficiency with 2x speedup compared to LIME. However, 
                limitations exist in out-of-distribution scenarios.
                """,
                "paper_title": "Interpretable Deep Learning",
                "paper_year": 2023,
                "section": "results",
                "similarity_score": 0.89,
                "paper_id": "paper2",
                "evidence_sentence": "Attention mechanisms inherently provide explanations",
                "evidence_score": 0.85
            },
            {
                "text": """
                Healthcare applications show promise with 95% accuracy. Financial sector 
                adoption is increasing. Regulatory requirements (GDPR, CCPA) drive XAI 
                implementation. Key implications include improved compliance and user trust.
                """,
                "paper_title": "XAI in Production",
                "paper_year": 2024,
                "section": "discussion",
                "similarity_score": 0.87,
                "paper_id": "paper3",
                "evidence_sentence": "Regulatory requirements drive XAI adoption",
                "evidence_score": 0.90
            }
        ]
    
    # ──────────────────────────────────────────────────────────────────────
    # Prompt Formatting Tests
    # ──────────────────────────────────────────────────────────────────────
    
    def test_format_sub_questions(self, generator):
        """Test sub-question formatting."""
        sub_qs = ["What is XAI?", "Why is it important?", "How to implement?"]
        formatted = generator._format_sub_questions(sub_qs)
        
        assert "1." in formatted
        assert "2." in formatted
        assert "3." in formatted
        assert "What is XAI?" in formatted
    
    def test_format_sub_questions_empty(self, generator):
        """Test formatting with no sub-questions."""
        formatted = generator._format_sub_questions([])
        
        assert formatted == "Not decomposed"
    
    def test_format_methodology_summary(self, generator):
        """Test methodology summary formatting."""
        from src.generation.inference_engine import MethodologyInsight
        
        insights = [
            MethodologyInsight(
                technique="SHAP",
                assumptions=["assumes independence"],
                constraints=["image domain"],
                scope="Classification",
                validation_method="User study"
            )
        ]
        
        formatted = generator._format_methodology_summary(insights)
        
        assert "SHAP" in formatted
        assert "independence" in formatted or "Classification" in formatted
    
    def test_format_findings_summary(self, generator):
        """Test findings summary formatting."""
        from src.generation.inference_engine import ExperimentalFinding
        
        findings = [
            ExperimentalFinding(
                finding="Achieves high performance",
                metrics={"accuracy": 0.94},
                conditions=["on ImageNet"],
                generalizability="high"
            )
        ]
        
        formatted = generator._format_findings_summary(findings)
        
        assert "Achieves high performance" in formatted
        assert "high" in formatted.lower()
    
    def test_format_metrics_summary(self, generator, sample_chunks):
        """Test metrics summary formatting."""
        formatted = generator._format_metrics_summary(sample_chunks)
        
        assert len(formatted) > 0
        # Should extract accuracy, precision, recall metrics
        assert "Accuracy" in formatted or "accuracy" in formatted.lower()
    
    def test_extract_scope(self, generator, sample_chunks):
        """Test scope extraction."""
        scope = generator._extract_scope(sample_chunks)
        
        assert len(scope) > 0
        assert "3" in scope or "paper" in scope.lower()
    
    def test_extract_techniques(self, generator):
        """Test technique extraction from inferences."""
        from src.generation.inference_engine import MethodologyInsight
        
        result = {
            "methodology_insights": [
                MethodologyInsight(
                    technique="SHAP",
                    assumptions=[],
                    constraints=[],
                    scope="",
                    validation_method=None
                )
            ]
        }
        
        techniques = generator._extract_techniques(result)
        
        assert "SHAP" in techniques
    
    # ──────────────────────────────────────────────────────────────────────
    # Main API Tests
    # ──────────────────────────────────────────────────────────────────────
    
    def test_generate_refined_answer_complete(self, generator, sample_chunks):
        """Test complete refined answer generation."""
        result = generator.generate_refined_answer(
            question="What are the latest advances in explainable AI?",
            sub_questions=[
                "What are main XAI techniques?",
                "Why is it important?",
                "What are applications?"
            ],
            chunks=sample_chunks
        )
        
        # Check structure
        assert "answer" in result
        assert "evidence_summary" in result
        assert "confidence" in result
        assert "structure_notes" in result
        assert "sources_count" in result
        assert "chunks_used" in result
        
        # Check content
        assert len(result["answer"]) > 500
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["sources_count"] > 0
        assert result["chunks_used"] > 0
    
    def test_answer_has_5_sections(self, generator, sample_chunks):
        """Test that answer has 5-section structure."""
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=sample_chunks
        )
        
        answer = result["answer"]
        
        # Check for section markers
        assert "EXECUTIVE SUMMARY" in answer or "SUMMARY" in answer.upper()
        assert "DETAILED ANALYSIS" in answer or "ANALYSIS" in answer.upper()
        assert "METHODOLOGICAL" in answer or "METHODOLOGY" in answer.upper()
        assert "IMPLICATIONS" in answer or "IMPLICATION" in answer.upper()
        assert "GAPS" in answer or "FUTURE" in answer.upper()
    
    def test_answer_includes_citations(self, generator, sample_chunks):
        """Test that answer includes citations."""
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=sample_chunks
        )
        
        answer = result["answer"]
        
        # Should reference papers or dates
        assert "2024" in answer or "2023" in answer or "According" in answer.lower() or "research" in answer.lower()
    
    def test_answer_includes_metrics(self, generator, sample_chunks):
        """Test that answer includes metrics."""
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=sample_chunks
        )
        
        answer = result["answer"]
        
        # Should include numeric metrics
        assert any(c.isdigit() for c in answer)
    
    def test_empty_chunks(self, generator):
        """Test handling of empty chunks."""
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=[]
        )
        
        # Should handle gracefully
        assert "answer" in result
    
    # ──────────────────────────────────────────────────────────────────────
    # Confidence Tests
    # ──────────────────────────────────────────────────────────────────────
    
    def test_confidence_with_good_evidence(self, generator, sample_chunks):
        """Test confidence with good evidence."""
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=sample_chunks
        )
        
        # With good evidence, confidence should be reasonable
        assert result["confidence"] > 0.3
    
    def test_confidence_with_few_chunks(self, generator):
        """Test confidence with few chunks."""
        chunks = [
            {
                "text": "Some text",
                "paper_title": "Paper",
                "paper_year": 2024,
                "section": "body",
                "similarity_score": 0.7,
                "paper_id": "p1"
            }
        ]
        
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=chunks
        )
        
        # Confidence should be lower with less evidence
        assert 0.0 <= result["confidence"] <= 1.0
    
    # ──────────────────────────────────────────────────────────────────────
    # Formatting Helper Tests
    # ──────────────────────────────────────────────────────────────────────
    
    def test_assess_evidence_quality_high(self, generator):
        """Test evidence quality assessment."""
        chunks = [
            {"similarity_score": 0.95},
            {"similarity_score": 0.93},
            {"similarity_score": 0.91}
        ]
        
        quality = generator._assess_evidence_quality(chunks)
        
        assert quality == "HIGH"
    
    def test_assess_evidence_quality_moderate(self, generator):
        """Test moderate evidence quality."""
        chunks = [
            {"similarity_score": 0.65},
            {"similarity_score": 0.60},
            {"similarity_score": 0.55}
        ]
        
        quality = generator._assess_evidence_quality(chunks)
        
        assert quality == "MODERATE"
    
    def test_assess_evidence_quality_low(self, generator):
        """Test low evidence quality."""
        chunks = [
            {"similarity_score": 0.45},
            {"similarity_score": 0.40}
        ]
        
        quality = generator._assess_evidence_quality(chunks)
        
        assert quality == "LOW"
    
    def test_assess_evidence_quality_no_chunks(self, generator):
        """Test with no chunks."""
        quality = generator._assess_evidence_quality([])
        
        assert quality == "NO_EVIDENCE"
    
    # ──────────────────────────────────────────────────────────────────────
    # Integration with InferenceEngine Tests
    # ──────────────────────────────────────────────────────────────────────
    
    def test_uses_inference_engine(self, generator, sample_chunks):
        """Test that generator uses InferenceEngine."""
        # Verify that inference engine is initialized
        assert generator.inference_engine is not None
        
        # Test that inferences are extracted
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=sample_chunks
        )
        
        assert result["evidence_summary"] is not None
    
    # ──────────────────────────────────────────────────────────────────────
    # Edge Cases
    # ──────────────────────────────────────────────────────────────────────
    
    def test_handle_chunks_with_missing_fields(self, generator):
        """Test handling chunks with missing fields."""
        chunks = [
            {
                "text": "Some text",
                # Missing other fields
            }
        ]
        
        # Should not crash
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=chunks
        )
        
        assert "answer" in result
    
    def test_handle_very_long_chunks(self, generator):
        """Test handling very long chunks."""
        long_text = "word " * 5000  # Very long text
        chunks = [
            {
                "text": long_text,
                "paper_title": "Paper",
                "paper_year": 2024,
                "section": "body",
                "similarity_score": 0.8,
                "paper_id": "p1"
            }
        ]
        
        # Should handle without crashing
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=chunks
        )
        
        assert "answer" in result
    
    def test_handle_special_characters(self, generator):
        """Test handling special characters in chunks."""
        chunks = [
            {
                "text": "Special chars: <, >, &, %, $, #, @, !, *",
                "paper_title": "Paper",
                "paper_year": 2024,
                "section": "body",
                "similarity_score": 0.8,
                "paper_id": "p1"
            }
        ]
        
        # Should handle special characters
        result = generator.generate_refined_answer(
            question="What is explainable AI?",
            sub_questions=["What are techniques?"],
            chunks=chunks
        )
        
        assert "answer" in result


class TestRefinedAnswerGeneratorWithVerification:
    """Test verification features."""
    
    @pytest.fixture
    def mock_llm(self):
        return MockLLM()
    
    @pytest.fixture
    def generator(self, mock_llm):
        return RefinedAnswerGenerator(mock_llm)
    
    def test_verification_prompt_structure(self, generator):
        """Test that verification prompt is well-structured."""
        assert "ORIGINAL QUESTION" in generator.EVIDENCE_VERIFICATION_PROMPT
        assert "GENERATED ANSWER" in generator.EVIDENCE_VERIFICATION_PROMPT
        assert "AVAILABLE EVIDENCE" in generator.EVIDENCE_VERIFICATION_PROMPT
        assert "VERIFIED CLAIMS" in generator.EVIDENCE_VERIFICATION_PROMPT
    
    def test_build_evidence_dump(self, generator):
        """Test evidence dump building."""
        chunks = [
            {
                "paper_title": "Paper 1",
                "paper_year": 2024,
                "section": "methodology",
                "similarity_score": 0.95,
                "text": "Some evidence text"
            },
            {
                "paper_title": "Paper 2",
                "paper_year": 2023,
                "section": "results",
                "similarity_score": 0.88,
                "text": "More evidence"
            }
        ]
        
        dump = generator._build_evidence_dump(chunks)
        
        assert "Paper 1" in dump
        assert "Paper 2" in dump
        assert "EVIDENCE 1" in dump
        assert "EVIDENCE 2" in dump


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
