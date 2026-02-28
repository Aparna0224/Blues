"""Unit tests for the Verification Agent (Stage 4)."""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.verification import VerificationAgent


class TestVerificationAgent:
    """Test cases for VerificationAgent."""

    @pytest.fixture
    def agent(self):
        """Create a VerificationAgent instance."""
        return VerificationAgent()

    # =========================================================================
    # Helper to build evidence items quickly
    # =========================================================================

    @staticmethod
    def _make_evidence(
        claim: str = "Test claim",
        score: float = 0.80,
        paper_id: str = "paper_1",
        paper_title: str = "Test Paper",
        year: int = 2023,
    ) -> dict:
        return {
            "claim": claim,
            "supporting_sentence": claim,
            "similarity_score": score,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "year": year,
        }

    # =========================================================================
    # Test 1 — Strong Query (high confidence, no warnings)
    # =========================================================================

    def test_strong_query_high_confidence(self, agent):
        """Strong evidence from diverse sources → high confidence, no warnings."""
        evidence = [
            self._make_evidence("AI shows clear diagnostic potential", 0.88, "p1", "Paper A", 2023),
            self._make_evidence("Deep learning aids medical imaging", 0.85, "p2", "Paper B", 2022),
            self._make_evidence("Neural networks useful for scans", 0.82, "p3", "Paper C", 2021),
            self._make_evidence("Transfer learning boosts results", 0.80, "p4", "Paper D", 2023),
            self._make_evidence("XAI builds clinician trust", 0.79, "p5", "Paper E", 2024),
        ]

        result = agent.verify({
            "query": "How does AI improve medical diagnosis?",
            "sub_questions": ["Q1", "Q2"],
            "evidence": evidence,
            "total_chunks_retrieved": 10,
        })

        assert result["confidence_score"] >= 0.75
        # Should have no weakness warnings (diversity is 5, avg sim > 0.65, density 0.5)
        assert "Weak evidence strength" not in result["warnings"]
        assert "Low source diversity" not in result["warnings"]
        assert "No supporting evidence found" not in result["warnings"]
        assert result["metrics"]["source_diversity"] == 5
        assert result["metrics"]["normalized_source_diversity"] == 1.0
        assert result["metrics"]["avg_similarity"] > 0.80
        assert result["metrics"]["conflicts_detected"] is False

    # =========================================================================
    # Test 2 — Weak Query (low confidence, warnings)
    # =========================================================================

    def test_weak_query_low_confidence(self, agent):
        """Weak similarity scores, single source → low confidence."""
        evidence = [
            self._make_evidence("Some vague mention of topic", 0.45, "p1", "Paper A", 2020),
            self._make_evidence("Tangentially related content", 0.50, "p1", "Paper A", 2020),
        ]

        result = agent.verify({
            "query": "Obscure niche question?",
            "sub_questions": ["Q1"],
            "evidence": evidence,
            "total_chunks_retrieved": 15,
        })

        assert result["confidence_score"] < 0.50
        assert result["confidence_score"] <= 0.50  # Case C cap
        assert "All evidence weakly related" in result["warnings"]
        assert "Low source diversity" in result["warnings"]
        assert result["metrics"]["source_diversity"] == 1
        assert result["metrics"]["avg_similarity"] < 0.55

    # =========================================================================
    # Test 3 — Conflicting Papers (conflict detected, reduced confidence)
    # =========================================================================

    def test_conflicting_evidence(self, agent):
        """Mixed polarity across claims → conflict detected, penalty applied."""
        evidence = [
            self._make_evidence(
                "Deep learning significantly improves diagnostic accuracy",
                0.82, "p1", "Paper A", 2023,
            ),
            self._make_evidence(
                "The model fails to generalize and is not effective on new data",
                0.78, "p2", "Paper B", 2022,
            ),
            self._make_evidence(
                "Results show clinical potential for adoption",
                0.75, "p3", "Paper C", 2021,
            ),
        ]

        result = agent.verify({
            "query": "Is deep learning effective for diagnosis?",
            "sub_questions": ["Q1", "Q2"],
            "evidence": evidence,
            "total_chunks_retrieved": 10,
        })

        assert result["metrics"]["conflicts_detected"] is True
        assert "Mixed findings across sources" in result["warnings"]
        # Confidence should be reduced by CONFLICT_PENALTY
        # Without penalty: 0.5*0.783 + 0.3*0.6 + 0.2*0.3 = 0.632
        # With penalty: 0.632 - 0.15 = 0.482
        assert result["confidence_score"] < 0.65

    # =========================================================================
    # Test 4 — No Evidence (confidence = 0)
    # =========================================================================

    def test_no_evidence(self, agent):
        """Empty evidence list → confidence 0, single warning."""
        result = agent.verify({
            "query": "Completely unknown topic?",
            "sub_questions": ["Q1"],
            "evidence": [],
            "total_chunks_retrieved": 0,
        })

        assert result["confidence_score"] == 0.0
        assert result["warnings"] == ["No supporting evidence found"]
        assert result["metrics"]["avg_similarity"] == 0.0
        assert result["metrics"]["source_diversity"] == 0
        assert result["metrics"]["normalized_source_diversity"] == 0.0
        assert result["metrics"]["evidence_density"] == 0.0
        assert result["metrics"]["conflicts_detected"] is False

    # =========================================================================
    # Metric unit tests
    # =========================================================================

    def test_avg_similarity_computation(self, agent):
        """Average similarity is arithmetic mean of scores."""
        evidence = [
            self._make_evidence(score=0.90),
            self._make_evidence(score=0.70),
            self._make_evidence(score=0.80),
        ]
        avg = agent._compute_avg_similarity(evidence)
        assert abs(avg - 0.80) < 1e-6

    def test_source_diversity_normalization(self, agent):
        """Source diversity is capped at 5 for normalization."""
        evidence = [
            self._make_evidence(paper_id=f"p{i}") for i in range(8)
        ]
        unique, normalized = agent._compute_source_diversity(evidence)
        assert unique == 8
        assert normalized == 1.0  # capped at min(8/5, 1.0)

    def test_evidence_density_zero_chunks(self, agent):
        """Evidence density is 0 when total_chunks_retrieved is 0."""
        evidence = [self._make_evidence()]
        density = agent._compute_evidence_density(evidence, total_chunks=0)
        assert density == 0.0

    def test_evidence_density_normal(self, agent):
        """Evidence density is claims / total chunks."""
        evidence = [self._make_evidence() for _ in range(3)]
        density = agent._compute_evidence_density(evidence, total_chunks=10)
        assert abs(density - 0.3) < 1e-6

    def test_conflict_detection_positive_negative(self, agent):
        """Positive + negative polarity across claims → conflict."""
        evidence = [
            self._make_evidence("This approach significantly improves accuracy"),
            self._make_evidence("This method fails to produce reliable results"),
        ]
        assert agent._detect_conflicts(evidence) is True

    def test_conflict_detection_no_conflict(self, agent):
        """Neutral academic prose → no conflict."""
        evidence = [
            self._make_evidence("AI aids diagnosis in many settings"),
            self._make_evidence("Deep learning shows potential for imaging"),
        ]
        assert agent._detect_conflicts(evidence) is False

    def test_conflict_detection_hedging_not_false_positive(self, agent):
        """Normal academic hedging words should NOT trigger a conflict."""
        evidence = [
            self._make_evidence("This approach shows promise, however further work is needed"),
            self._make_evidence("Despite some limitations, the model performs well"),
            self._make_evidence("Results are limited to a single dataset"),
        ]
        assert agent._detect_conflicts(evidence) is False

    def test_confidence_clamped_to_0_1(self, agent):
        """Confidence score is always between 0 and 1."""
        # Very weak evidence with penalties should not go below 0
        evidence = [
            self._make_evidence("fails to produce results and is not effective", 0.20, "p1"),
            self._make_evidence("significantly improves nothing does not improve", 0.15, "p1"),
        ]

        result = agent.verify({
            "query": "test",
            "sub_questions": [],
            "evidence": evidence,
            "total_chunks_retrieved": 100,
        })

        assert result["confidence_score"] >= 0.0
        assert result["confidence_score"] <= 1.0

    # =========================================================================
    # build_verification_input tests
    # =========================================================================

    def test_build_verification_input(self, agent):
        """build_verification_input correctly maps chunk fields."""
        plan = {"sub_questions": ["Q1", "Q2"]}
        chunks = [
            {
                "text": "Full chunk text here",
                "evidence_sentence": "Key evidence sentence",
                "similarity_score": 0.85,
                "paper_id": "p1",
                "paper_title": "Paper A",
                "paper_year": 2023,
            },
            {
                "text": "Another chunk with no evidence sentence",
                "similarity_score": 0.72,
                "paper_id": "p2",
                "paper_title": "Paper B",
                "paper_year": 2022,
            },
        ]

        vi = agent.build_verification_input("test query", plan, chunks)

        assert vi["query"] == "test query"
        assert vi["sub_questions"] == ["Q1", "Q2"]
        # No _total_chunks_searched → falls back to len(chunks)
        assert vi["total_chunks_retrieved"] == 2
        assert len(vi["evidence"]) == 2

        # First chunk: has evidence_sentence → used as claim
        assert vi["evidence"][0]["claim"] == "Key evidence sentence"
        assert vi["evidence"][0]["supporting_sentence"] == "Key evidence sentence"
        assert vi["evidence"][0]["similarity_score"] == 0.85

        # Second chunk: no evidence_sentence → falls back to text[:300]
        assert vi["evidence"][1]["claim"] == "Another chunk with no evidence sentence"
        assert vi["evidence"][1]["supporting_sentence"] == ""

    def test_build_verification_input_uses_total_pool(self, agent):
        """build_verification_input uses _total_chunks_searched as denominator."""
        plan = {"sub_questions": ["Q1"]}
        chunks = [
            {
                "text": "Chunk text",
                "similarity_score": 0.80,
                "paper_id": "p1",
                "paper_title": "Paper A",
                "paper_year": 2023,
                "_total_chunks_searched": 648,
            },
        ]

        vi = agent.build_verification_input("test query", plan, chunks)

        # Should use _total_chunks_searched, NOT len(chunks)
        assert vi["total_chunks_retrieved"] == 648

    def test_build_verification_input_empty_chunks(self, agent):
        """build_verification_input with empty chunks."""
        vi = agent.build_verification_input("q", {"sub_questions": []}, [])
        assert vi["evidence"] == []
        assert vi["total_chunks_retrieved"] == 0

    # =========================================================================
    # format_verification_output tests
    # =========================================================================

    def test_format_output_contains_key_sections(self, agent):
        """Formatted output contains all required sections."""
        result = {
            "confidence_score": 0.72,
            "metrics": {
                "avg_similarity": 0.78,
                "source_diversity": 3,
                "normalized_source_diversity": 0.6,
                "evidence_density": 0.58,
                "conflicts_detected": False,
            },
            "warnings": ["Low source diversity"],
        }
        output = agent.format_verification_output(result)

        assert "VERIFICATION SUMMARY" in output
        assert "Confidence Score: 0.72" in output
        assert "Low source diversity" in output
        assert "Average Similarity" in output
        assert "Source Diversity" in output
        assert "Evidence Density" in output
        assert "Conflicts Detected" in output

    def test_format_output_high_confidence_indicator(self, agent):
        """High confidence shows green indicator."""
        result = {
            "confidence_score": 0.85,
            "metrics": {"avg_similarity": 0.9, "source_diversity": 5,
                        "normalized_source_diversity": 1.0,
                        "evidence_density": 0.8, "conflicts_detected": False},
            "warnings": [],
        }
        output = agent.format_verification_output(result)
        assert "HIGH" in output
        assert "No warnings" in output

    def test_format_output_low_confidence_indicator(self, agent):
        """Low confidence shows red indicator."""
        result = {
            "confidence_score": 0.30,
            "metrics": {"avg_similarity": 0.4, "source_diversity": 1,
                        "normalized_source_diversity": 0.2,
                        "evidence_density": 0.1, "conflicts_detected": True},
            "warnings": ["Weak evidence strength", "Mixed findings across sources"],
        }
        output = agent.format_verification_output(result)
        assert "LOW" in output
