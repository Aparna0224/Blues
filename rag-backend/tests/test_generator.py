"""Unit tests for grouped answer generation formatting."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.generation.generator import AnswerGenerator


class _FakeEvidenceExtractor:
    def select_best_sentence(self, query, text):
        return {
            "best_sentence": "RAG improves factual grounding by using retrieved documents.",
            "best_score": 0.81,
            "below_threshold": False,
        }


class TestAnswerGenerator:
    def test_grouped_answer_includes_location_and_multiline_claim(self, monkeypatch):
        generator = AnswerGenerator()

        plan = {
            "main_question": "what is the use of rag in ai",
            "sub_questions": ["How does RAG help AI models?"],
        }

        chunk = {
            "chunk_id": "c1",
            "text": (
                "RAG combines retrieval with generation for grounded outputs. "
                "RAG improves factual grounding by using retrieved documents. "
                "This often reduces hallucinations in practical AI assistants."
            ),
            "paper_id": "p1",
            "paper_title": "RAG Study",
            "paper_year": 2025,
            "similarity_score": 0.74,
            "evidence_sentence": "RAG improves factual grounding by using retrieved documents.",
            "evidence_score": 0.81,
            "metadata": {
                "section": "methodology",
                "category": "rag",
            },
        }

        monkeypatch.setattr(
            generator,
            "_assign_chunks_to_subquestions",
            lambda sub_questions, chunks: {sub_questions[0]: [chunk]},
        )
        monkeypatch.setattr("src.evidence.extractor.EvidenceExtractor", _FakeEvidenceExtractor)

        output = generator.generate_grouped_answer(plan, [chunk])

        assert "📌 Evidence Units (Grouped by Paper)" in output
        assert "Section: Methodology" in output
        assert "Location: sentences" in output
        assert "Relevance:" in output
        assert "Confidence:" in output
        assert "RAG combines retrieval with generation for grounded outputs." in output
        assert "RAG improves factual grounding by using retrieved documents." in output
        assert "reduces hallucinations" in output
        assert "⚠️ Cross-Paper Conflict Analysis" in output
        assert "Comparison Summary" in output

    def test_section_detection_introduction_not_misclassified_as_methodology(
        self, monkeypatch
    ):
        """
        Test that Introduction content is NOT falsely labeled as Methodology.
        
        Issue: Content saying "this paper's approach to the problem" should be
        Introduction (motivation/problem statement), not Methodology.
        
        Fix: Priority-based detection with explicit headers first, then strong
        indicators, then weak indicators as last resort.
        """
        generator = AnswerGenerator()

        # Chunk with Introduction content (should NOT be classified as Methodology)
        intro_chunk = {
            "chunk_id": "intro_1",
            "text": (
                "## Introduction\n\n"
                "Deep learning has revolutionized AI. This paper addresses the problem "
                "of efficient model training. Our research question is: how can we "
                "reduce training time? The motivation behind this work is to make "
                "advanced AI accessible to resource-constrained environments. "
                "This paper's approach to the problem focuses on optimization."
            ),
            "paper_id": "p1",
            "paper_title": "Efficient Training Study",
            "paper_year": 2025,
            "similarity_score": 0.85,
            "metadata": {"section": "introduction", "category": "neural_networks"},
        }

        # Test that explicit header detection works
        inferred_intro, was_corrected = generator._resolve_true_section(intro_chunk)
        assert (
            inferred_intro.lower() == "introduction"
        ), f"Expected 'introduction', got '{inferred_intro}'"

        # Chunk with Methodology content (should be classified as Methodology)
        method_chunk = {
            "chunk_id": "method_1",
            "text": (
                "## Methodology\n\n"
                "We implement a novel algorithm for network training. "
                "The hyperparameter settings are: learning_rate=0.001, "
                "batch_size=32, epochs=100. Our training process consists of "
                "three phases. The pseudo-code is presented below: "
                "for each epoch: forward pass, backward pass, weight update."
            ),
            "paper_id": "p1",
            "paper_title": "Efficient Training Study",
            "paper_year": 2025,
            "similarity_score": 0.82,
            "metadata": {"section": "methodology", "category": "neural_networks"},
        }

        # Test that methodology detection works
        inferred_method, was_corrected = generator._resolve_true_section(method_chunk)
        assert (
            inferred_method.lower() == "methodology"
        ), f"Expected 'methodology', got '{inferred_method}'"

        # Chunk with Results content (should NOT be confused with Methodology)
        results_chunk = {
            "chunk_id": "results_1",
            "text": (
                "## Results\n\n"
                "Our model achieved state-of-the-art (SOTA) performance. "
                "The accuracy: 96.5%, precision: 97.2%, recall: 95.8%, "
                "f1 score: 96.5% on the test set."
            ),
            "paper_id": "p1",
            "paper_title": "Efficient Training Study",
            "paper_year": 2025,
            "similarity_score": 0.88,
            "metadata": {"section": "results", "category": "neural_networks"},
        }

        # Test that results detection works
        inferred_results, was_corrected = generator._resolve_true_section(results_chunk)
        assert (
            inferred_results.lower() == "results"
        ), f"Expected 'results', got '{inferred_results}'"

