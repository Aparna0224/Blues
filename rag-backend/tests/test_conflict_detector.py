"""Unit tests for comparison conflict detector."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.comparison.conflict_detector import ConflictDetector


class TestConflictDetector:
    def test_detect_conflict_across_papers(self):
        units = [
            {
                "paper_id": "p1",
                "paper_title": "Paper A",
                "section": "Methodology",
                "claim": "RAG improves factual accuracy in question answering.",
                "text": "RAG improves factual accuracy in question answering.",
            },
            {
                "paper_id": "p2",
                "paper_title": "Paper B",
                "section": "Results",
                "claim": "RAG fails to improve factual accuracy in question answering.",
                "text": "RAG fails to improve factual accuracy in question answering.",
            },
        ]

        conflicts = ConflictDetector.detect_conflicts(units)
        assert len(conflicts) >= 1
        assert conflicts[0]["type"] in {"Conceptual", "Methodological", "Empirical"}
        assert 0.0 <= conflicts[0]["strength"] <= 1.0

    def test_comparison_summary_counts(self):
        units = [
            {
                "paper_id": "p1",
                "paper_title": "Paper A",
                "section": "Methodology",
                "claim": "RAG improves factual accuracy in question answering.",
                "text": "RAG improves factual accuracy in question answering.",
            },
            {
                "paper_id": "p2",
                "paper_title": "Paper B",
                "section": "Results",
                "claim": "RAG fails to improve factual accuracy in question answering.",
                "text": "RAG fails to improve factual accuracy in question answering.",
            },
        ]
        conflicts = ConflictDetector.detect_conflicts(units)
        summary = ConflictDetector.comparison_summary(units, conflicts)

        assert "supporting_clusters" in summary
        assert "conflicting_clusters" in summary
        assert summary["consensus_level"] in {"High", "Medium", "Low"}
