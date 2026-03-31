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

        assert "📍 Location: section=methodology | category=rag" in output
        assert "RAG combines retrieval with generation for grounded outputs." in output
        assert "RAG improves factual grounding by using retrieved documents." in output
        assert "reduces hallucinations" in output
