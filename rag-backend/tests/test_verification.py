"""Unit tests for the Verification Agent v2 (Stage 4).

Covers:
  - Full pipeline tests (strong, weak, conflicting, no-evidence)
  - Claim deduplication
  - Claim relevance filtering
  - Similarity threshold gating
  - Cross-paper conflict detection
  - Confidence calibration (weak-similarity multiplier)
  - Evidence density (denominator = top-k returned)
  - Audit log correctness
  - build_verification_input
  - format_verification_output
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.verification import VerificationAgent


class TestVerificationAgent:
    """Test cases for VerificationAgent v2."""

    @pytest.fixture
    def agent(self):
        return VerificationAgent()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _e(
        claim: str = "Test claim about a method",
        score: float = 0.80,
        paper_id: str = "p1",
        paper_title: str = "Test Paper",
        year: int = 2023,
    ) -> dict:
        """Shorthand evidence builder."""
        return {
            "claim": claim,
            "supporting_sentence": claim,
            "similarity_score": score,
            "paper_id": paper_id,
            "paper_title": paper_title,
            "year": year,
        }

    # =================================================================
    # 1. Full pipeline — strong query
    # =================================================================

    def test_strong_query_high_confidence(self, agent):
        """Diverse, high-similarity, domain-relevant claims → HIGH."""
        evidence = [
            self._e("Deep learning model for diagnostic imaging", 0.88, "p1"),
            self._e("Attention-based neural network for classification", 0.85, "p2"),
            self._e("SHAP explanations applied to clinical prediction", 0.82, "p3"),
            self._e("Transfer learning approach for medical imaging", 0.80, "p4"),
            self._e("Saliency maps improve interpretability of diagnosis", 0.79, "p5"),
        ]
        result = agent.verify({
            "query": "XAI in medical diagnosis",
            "sub_questions": ["Q1", "Q2"],
            "evidence": evidence,
            "total_chunks_retrieved": 15,
        })

        assert result["confidence_score"] >= 0.70
        assert result["metrics"]["conflicts_detected"] is False
        assert result["metrics"]["source_diversity"] == 5
        assert "audit" in result
        assert result["audit"]["total_claims_received"] == 5
        assert "Low source diversity" not in result["warnings"]

    # =================================================================
    # 2. Full pipeline — weak query
    # =================================================================

    def test_weak_query_low_confidence(self, agent):
        """Low similarity, single source → LOW confidence."""
        evidence = [
            self._e("Some vague mention of a method", 0.45, "p1"),
            self._e("Tangentially related technique discussion", 0.50, "p1"),
        ]
        result = agent.verify({
            "query": "Obscure niche?",
            "sub_questions": ["Q1"],
            "evidence": evidence,
            "total_chunks_retrieved": 15,
        })

        assert result["confidence_score"] < 0.50
        assert "Low source diversity" in result["warnings"]
        assert result["metrics"]["source_diversity"] == 1

    # =================================================================
    # 3. Full pipeline — conflicting evidence (cross-paper)
    # =================================================================

    def test_conflicting_evidence_cross_paper(self, agent):
        """Positive in paper A, negative in paper B → conflict."""
        evidence = [
            self._e(
                "This model significantly improves diagnostic accuracy",
                0.82, "p1",
            ),
            self._e(
                "The approach fails to generalise and is not effective",
                0.78, "p2",
            ),
            self._e(
                "Neural network for clinical imaging", 0.75, "p3",
            ),
        ]
        result = agent.verify({
            "query": "Is deep learning effective?",
            "sub_questions": ["Q1"],
            "evidence": evidence,
            "total_chunks_retrieved": 10,
        })

        assert result["metrics"]["conflicts_detected"] is True
        assert "Mixed findings across sources" in result["warnings"]

    # =================================================================
    # 4. Full pipeline — no evidence
    # =================================================================

    def test_no_evidence(self, agent):
        """Empty evidence → confidence 0, single warning, audit zeros."""
        result = agent.verify({
            "query": "Unknown",
            "sub_questions": [],
            "evidence": [],
            "total_chunks_retrieved": 0,
        })

        assert result["confidence_score"] == 0.0
        assert result["warnings"] == ["No supporting evidence found"]
        assert result["audit"]["total_claims_received"] == 0
        assert result["audit"]["claims_rejected"] == 0

    # =================================================================
    # 5. Deduplication
    # =================================================================

    def test_deduplication_removes_identical_claims(self, agent):
        """Exact-duplicate claims are collapsed, keeping higher score."""
        evidence = [
            self._e("Neural network model for diagnosis", 0.80, "p1"),
            self._e("Neural network model for diagnosis", 0.85, "p2"),
        ]
        deduped = agent._deduplicate_claims(evidence)
        assert len(deduped) == 1
        assert deduped[0]["similarity_score"] == 0.85

    def test_deduplication_keeps_distinct_claims(self, agent):
        """Substantially different claims survive dedup."""
        evidence = [
            self._e("SHAP applied to clinical predictions", 0.80, "p1"),
            self._e("Attention maps for radiology imaging", 0.78, "p2"),
        ]
        deduped = agent._deduplicate_claims(evidence)
        assert len(deduped) == 2

    # =================================================================
    # 6. Relevance filtering
    # =================================================================

    def test_relevance_filter_keeps_domain_claims(self, agent):
        """Claims containing domain terms pass the filter."""
        evidence = [
            self._e("Saliency maps improve model interpretability", 0.82),
            self._e("Legal and privacy aspects are rising", 0.80),
        ]
        relevant = agent._filter_relevant_claims(evidence)
        assert len(relevant) == 1
        assert "saliency" in relevant[0]["claim"].lower()

    def test_relevance_filter_rejects_generic(self, agent):
        """Pure motivational sentences are filtered out."""
        evidence = [
            self._e("Consequently a huge motivation is rising", 0.80),
            self._e("There are complex sources of data", 0.78),
        ]
        relevant = agent._filter_relevant_claims(evidence)
        assert len(relevant) == 0

    def test_relevance_fallback_when_all_filtered(self, agent):
        """If all claims are generic, verify() falls back to deduped set."""
        evidence = [
            self._e("Consequently a huge motivation is rising", 0.80, "p1"),
            self._e("There are complex sources of data", 0.78, "p2"),
        ]
        result = agent.verify({
            "query": "test",
            "sub_questions": [],
            "evidence": evidence,
            "total_chunks_retrieved": 10,
        })

        # Should still produce a result (falls back to deduped)
        assert result["confidence_score"] > 0
        assert result["audit"]["claims_after_relevance_filter"] == 0
        assert "No domain-relevant claims found" in result["warnings"]

    # =================================================================
    # 7. Similarity gating
    # =================================================================

    def test_similarity_gating_excludes_weak(self, agent):
        """Claims below 0.70 are excluded when stronger ones exist."""
        evidence = [
            self._e("Deep learning model for diagnosis", 0.85, "p1"),
            self._e("Neural network technique for imaging", 0.60, "p2"),
            self._e("Machine learning approach for clinical prediction", 0.75, "p3"),
        ]
        result = agent.verify({
            "query": "test",
            "sub_questions": [],
            "evidence": evidence,
            "total_chunks_retrieved": 10,
        })

        # Only 2 claims above 0.70
        assert result["audit"]["claims_above_similarity_threshold"] == 2
        assert result["audit"]["claims_used_for_scoring"] == 2
        # Average should be (0.85+0.75)/2 = 0.80
        assert abs(result["metrics"]["avg_similarity"] - 0.80) < 0.01

    # =================================================================
    # 8. Cross-paper conflict detection
    # =================================================================

    def test_same_paper_contrast_no_conflict(self, agent):
        """Positive and negative from same paper → NOT a conflict."""
        evidence = [
            self._e("This significantly improves accuracy", 0.82, "p1"),
            self._e("However the method fails to generalise", 0.78, "p1"),
        ]
        assert agent._detect_conflicts(evidence) is False

    def test_cross_paper_conflict(self, agent):
        """Positive in p1, negative in p2 → conflict."""
        evidence = [
            self._e("This approach significantly improves results", 0.82, "p1"),
            self._e("The method is not effective in practice", 0.78, "p2"),
        ]
        assert agent._detect_conflicts(evidence) is True

    def test_no_polarity_no_conflict(self, agent):
        """Neutral academic prose → no conflict."""
        evidence = [
            self._e("This study discusses the model architecture", 0.80, "p1"),
            self._e("The approach uses attention for imaging", 0.78, "p2"),
        ]
        assert agent._detect_conflicts(evidence) is False

    def test_hedging_no_false_positive(self, agent):
        """Normal hedging words must NOT trigger conflict."""
        evidence = [
            self._e("However further work is needed on the model", 0.80, "p1"),
            self._e("Despite limitations the technique shows promise", 0.78, "p2"),
            self._e("Results are limited to a single dataset", 0.75, "p3"),
        ]
        assert agent._detect_conflicts(evidence) is False

    # =================================================================
    # 9. Confidence calibration
    # =================================================================

    def test_weak_similarity_multiplier(self, agent):
        """avg_similarity < 0.65 triggers 0.7x multiplier."""
        evidence = [
            self._e("Some method for diagnosis", 0.55, "p1"),
            self._e("An approach to classification", 0.58, "p2"),
            self._e("A technique for prediction", 0.52, "p3"),
        ]
        result = agent.verify({
            "query": "test",
            "sub_questions": [],
            "evidence": evidence,
            "total_chunks_retrieved": 10,
        })

        # avg_sim ≈ 0.55, below 0.65 → multiplier applied
        assert "Weak evidence strength" in result["warnings"] or \
               "All evidence weakly related" in result["warnings"]

    def test_confidence_clamped_0_1(self, agent):
        """Confidence is always in [0, 1]."""
        evidence = [
            self._e("fails to produce results, not effective", 0.20, "p1"),
            self._e("significantly improves nothing, does not improve", 0.15, "p2"),
        ]
        result = agent.verify({
            "query": "test",
            "sub_questions": [],
            "evidence": evidence,
            "total_chunks_retrieved": 100,
        })
        assert 0.0 <= result["confidence_score"] <= 1.0

    # =================================================================
    # 10. Evidence density
    # =================================================================

    def test_evidence_density_uses_top_k(self, agent):
        """Density = relevant_claims / total_chunks_retrieved (top-k)."""
        evidence = [self._e() for _ in range(3)]
        density = agent._compute_evidence_density(evidence, total_chunks=10)
        assert abs(density - 0.3) < 1e-6

    def test_evidence_density_zero_chunks(self, agent):
        """Density is 0 when total_chunks_retrieved is 0."""
        density = agent._compute_evidence_density([self._e()], total_chunks=0)
        assert density == 0.0

    def test_evidence_density_capped_at_1(self, agent):
        """Density cannot exceed 1.0."""
        evidence = [self._e() for _ in range(20)]
        density = agent._compute_evidence_density(evidence, total_chunks=10)
        assert density == 1.0

    # =================================================================
    # 11. Source diversity
    # =================================================================

    def test_source_diversity_normalization(self, agent):
        """Diversity capped at 5 for normalisation."""
        evidence = [self._e(paper_id=f"p{i}") for i in range(8)]
        unique, normalised = agent._compute_source_diversity(evidence)
        assert unique == 8
        assert normalised == 1.0

    # =================================================================
    # 12. Audit log
    # =================================================================

    def test_audit_log_completeness(self, agent):
        """Audit log contains all required fields."""
        evidence = [
            self._e("Deep learning model for diagnosis", 0.85, "p1"),
            self._e("Deep learning model for diagnosis", 0.80, "p1"),  # dup
            self._e("Motivation and privacy concerns only", 0.75, "p2"),  # generic
            self._e("Attention technique for imaging", 0.65, "p3"),  # below sim threshold
            self._e("SHAP approach for clinical prediction", 0.78, "p4"),  # good
        ]
        result = agent.verify({
            "query": "test",
            "sub_questions": [],
            "evidence": evidence,
            "total_chunks_retrieved": 15,
        })

        audit = result["audit"]
        assert audit["total_claims_received"] == 5
        assert audit["claims_after_dedup"] <= 5
        assert audit["claims_after_relevance_filter"] <= audit["claims_after_dedup"]
        assert audit["claims_used_for_scoring"] <= audit["claims_after_relevance_filter"] or \
               audit["claims_after_relevance_filter"] == 0
        assert audit["claims_rejected"] == 5 - audit["claims_used_for_scoring"]

    # =================================================================
    # 13. build_verification_input
    # =================================================================

    def test_build_verification_input_mapping(self, agent):
        """Correctly maps chunk fields to verification schema."""
        plan = {"sub_questions": ["Q1", "Q2"]}
        chunks = [
            {
                "text": "Full chunk text",
                "evidence_sentence": "Key evidence sentence",
                "similarity_score": 0.85,
                "paper_id": "p1",
                "paper_title": "Paper A",
                "paper_year": 2023,
            },
            {
                "text": "Another chunk no evidence sentence",
                "similarity_score": 0.72,
                "paper_id": "p2",
                "paper_title": "Paper B",
                "paper_year": 2022,
            },
        ]

        vi = agent.build_verification_input("test query", plan, chunks)

        assert vi["query"] == "test query"
        assert vi["sub_questions"] == ["Q1", "Q2"]
        assert vi["total_chunks_retrieved"] == 2  # len(chunks)
        assert len(vi["evidence"]) == 2
        assert vi["evidence"][0]["claim"] == "Key evidence sentence"
        assert vi["evidence"][1]["claim"] == "Another chunk no evidence sentence"
        assert vi["evidence"][1]["supporting_sentence"] == ""

    def test_build_verification_input_empty(self, agent):
        """Empty chunks → empty evidence, total = 0."""
        vi = agent.build_verification_input("q", {"sub_questions": []}, [])
        assert vi["evidence"] == []
        assert vi["total_chunks_retrieved"] == 0

    def test_build_verification_input_skips_below_threshold(self, agent):
        """Chunks flagged below evidence threshold should not be included for scoring."""
        chunks = [
            {
                "text": "Relevant chunk",
                "evidence_sentence": "Relevant claim",
                "similarity_score": 0.82,
                "evidence_score": 0.79,
                "paper_id": "p1",
                "paper_title": "Paper A",
                "paper_year": 2024,
                "evidence_below_threshold": False,
            },
            {
                "text": "Weak chunk",
                "evidence_sentence": "Weak claim",
                "similarity_score": 0.9,
                "evidence_score": 0.3,
                "paper_id": "p2",
                "paper_title": "Paper B",
                "paper_year": 2023,
                "evidence_below_threshold": True,
            },
        ]

        vi = agent.build_verification_input("test", {"sub_questions": []}, chunks)
        assert len(vi["evidence"]) == 1
        assert vi["evidence"][0]["paper_id"] == "p1"

    def test_build_verification_input_uses_conservative_effective_score(self, agent):
        """Effective similarity should use min(chunk_similarity, evidence_score)."""
        chunks = [
            {
                "text": "Chunk",
                "evidence_sentence": "Sentence",
                "similarity_score": 0.86,
                "evidence_score": 0.62,
                "paper_id": "p1",
                "paper_title": "Paper A",
                "paper_year": 2024,
            }
        ]

        vi = agent.build_verification_input("test", {"sub_questions": []}, chunks)
        assert len(vi["evidence"]) == 1
        assert abs(vi["evidence"][0]["similarity_score"] - 0.62) < 1e-9

    # =================================================================
    # 14. format_verification_output
    # =================================================================

    def test_format_output_contains_all_sections(self, agent):
        """Formatted output includes metrics, warnings, and audit."""
        result = {
            "confidence_score": 0.72,
            "metrics": {
                "avg_similarity": 0.78,
                "source_diversity": 3,
                "normalized_source_diversity": 0.6,
                "evidence_density": 0.58,
                "conflicts_detected": False,
            },
            "warnings": ["Sparse evidence coverage"],
            "audit": {
                "total_claims_received": 15,
                "claims_after_dedup": 12,
                "claims_after_relevance_filter": 10,
                "claims_above_similarity_threshold": 9,
                "claims_used_for_scoring": 9,
                "claims_rejected": 6,
            },
        }
        output = agent.format_verification_output(result)

        assert "VERIFICATION SUMMARY" in output
        assert "Confidence Score: 0.72" in output
        assert "Sparse evidence coverage" in output
        assert "Average Similarity" in output
        assert "Audit" in output
        assert "Claims Received" in output
        assert "After Deduplication" in output
        assert "After Relevance Filter" in output
        assert "Rejected" in output

    def test_format_output_high_indicator(self, agent):
        """HIGH confidence shows green indicator."""
        result = {
            "confidence_score": 0.85,
            "metrics": {"avg_similarity": 0.9, "source_diversity": 5,
                        "normalized_source_diversity": 1.0,
                        "evidence_density": 0.8, "conflicts_detected": False},
            "warnings": [],
            "audit": {},
        }
        output = agent.format_verification_output(result)
        assert "HIGH" in output
        assert "No warnings" in output

    def test_format_output_low_indicator(self, agent):
        """LOW confidence shows red indicator."""
        result = {
            "confidence_score": 0.30,
            "metrics": {"avg_similarity": 0.4, "source_diversity": 1,
                        "normalized_source_diversity": 0.2,
                        "evidence_density": 0.1, "conflicts_detected": True},
            "warnings": ["Weak evidence strength"],
            "audit": {},
        }
        output = agent.format_verification_output(result)
        assert "LOW" in output
