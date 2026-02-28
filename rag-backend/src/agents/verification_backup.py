"""Verification Agent for Stage 4 — Deterministic reliability estimation.

Evaluates the reliability of evidence-backed answers using:
  - Average similarity score
  - Evidence density
  - Source diversity (normalized)
  - Conflict detection (keyword-based)

Produces a deterministic confidence score with structured warnings.

MUST NOT:
  - Call database or LLM
  - Re-embed or re-rank text
  - Modify the answer
  - Call any external service
"""

from typing import List, Dict, Any


class VerificationAgent:
    """
    Deterministic post-answer verification agent.

    Receives structured evidence from the answer generation step and
    computes quantitative reliability metrics without any LLM or
    retrieval calls.

    Input contract::

        {
          "query": "...",
          "sub_questions": [...],
          "evidence": [
            {
              "claim": "...",
              "supporting_sentence": "...",
              "similarity_score": 0.81,
              "paper_id": "...",
              "paper_title": "...",
              "year": 2023
            }
          ],
          "total_chunks_retrieved": 12
        }

    Output contract::

        {
          "confidence_score": 0.72,
          "metrics": {
            "avg_similarity": 0.78,
            "source_diversity": 3,
            "normalized_source_diversity": 0.6,
            "evidence_density": 0.58,
            "conflicts_detected": false
          },
          "warnings": ["Low source diversity"]
        }
    """

    # ── Confidence formula weights ───────────────────────────────
    WEIGHT_SIMILARITY = 0.5
    WEIGHT_DIVERSITY = 0.3
    WEIGHT_DENSITY = 0.2

    # ── Source diversity normalization cap ────────────────────────
    DIVERSITY_CAP = 5

    # ── Conflict detection dictionaries ──────────────────────────
    # Only strong, unambiguous polarity terms.  Academic hedging
    # words like "however", "limited", "despite" are removed to
    # avoid false positives on normal scholarly prose.
    POSITIVE_TERMS = [
        "significantly improves",
        "significantly increases",
        "significantly reduces",
        "outperforms",
        "superior to",
        "strongly effective",
        "highly effective",
        "demonstrates clear benefit",
    ]
    NEGATIVE_TERMS = [
        "does not improve",
        "fails to",
        "ineffective",
        "does not reduce",
        "no significant difference",
        "inferior to",
        "underperforms",
        "no benefit",
        "not effective",
    ]

    # ── Edge-case penalties ──────────────────────────────────────
    SINGLE_SOURCE_PENALTY = 0.10
    CONFLICT_PENALTY = 0.15

    def verify(self, verification_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run deterministic verification on structured evidence.

        Args:
            verification_input: Dict following the input contract above.

        Returns:
            Dict following the output contract above.
        """
        evidence = verification_input.get("evidence", [])
        total_chunks = verification_input.get("total_chunks_retrieved", 0)

        # ── Case A: No evidence ──────────────────────────────────
        if not evidence:
            return {
                "confidence_score": 0.0,
                "metrics": {
                    "avg_similarity": 0.0,
                    "source_diversity": 0,
                    "normalized_source_diversity": 0.0,
                    "evidence_density": 0.0,
                    "conflicts_detected": False,
                },
                "warnings": ["No supporting evidence found"],
            }

        # ── Compute raw metrics ──────────────────────────────────
        avg_similarity = self._compute_avg_similarity(evidence)
        source_diversity, norm_diversity = self._compute_source_diversity(evidence)
        evidence_density = self._compute_evidence_density(evidence, total_chunks)
        conflicts_detected = self._detect_conflicts(evidence)

        # ── Base confidence score ────────────────────────────────
        confidence = (
            self.WEIGHT_SIMILARITY * avg_similarity
            + self.WEIGHT_DIVERSITY * norm_diversity
            + self.WEIGHT_DENSITY * evidence_density
        )

        # ── Edge-case penalties ──────────────────────────────────
        warnings: List[str] = []

        # Case B — Single source
        if source_diversity == 1:
            confidence -= self.SINGLE_SOURCE_PENALTY
            warnings.append("Low source diversity")

        # Case C — All evidence weakly related
        similarity_scores = [e.get("similarity_score", 0) for e in evidence]
        if max(similarity_scores) < 0.60:
            confidence = min(confidence, 0.5)
            warnings.append("All evidence weakly related")

        # Case D — Conflict detected
        if conflicts_detected:
            confidence -= self.CONFLICT_PENALTY
            warnings.append("Mixed findings across sources")

        # ── Warning generation (threshold-based) ─────────────────
        if avg_similarity < 0.65 and "All evidence weakly related" not in warnings:
            warnings.append("Weak evidence strength")

        if source_diversity < 2 and "Low source diversity" not in warnings:
            warnings.append("Low source diversity")

        if evidence_density < 0.3:
            warnings.append("Sparse evidence coverage")

        # ── Clamp to [0, 1] ──────────────────────────────────────
        confidence = max(0.0, min(confidence, 1.0))

        return {
            "confidence_score": round(confidence, 4),
            "metrics": {
                "avg_similarity": round(avg_similarity, 4),
                "source_diversity": source_diversity,
                "normalized_source_diversity": round(norm_diversity, 4),
                "evidence_density": round(evidence_density, 4),
                "conflicts_detected": conflicts_detected,
            },
            "warnings": warnings,
        }

    # ─────────────────────────────────────────────────────────────
    # Metric computations
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_avg_similarity(evidence: List[Dict[str, Any]]) -> float:
        """Metric 1 — Average similarity score across all claims."""
        scores = [e.get("similarity_score", 0) for e in evidence]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def _compute_source_diversity(
        self, evidence: List[Dict[str, Any]]
    ) -> tuple:
        """
        Metric 3 — Source diversity (unique papers).

        Returns:
            (unique_sources, normalized_diversity)
        """
        paper_ids = [e.get("paper_id", "") for e in evidence if e.get("paper_id")]
        unique_sources = len(set(paper_ids))
        normalized = min(unique_sources / self.DIVERSITY_CAP, 1.0)
        return unique_sources, normalized

    @staticmethod
    def _compute_evidence_density(
        evidence: List[Dict[str, Any]], total_chunks: int
    ) -> float:
        """Metric 2 — Evidence density (claims / total chunks retrieved)."""
        if total_chunks == 0:
            return 0.0
        return len(evidence) / total_chunks

    def _detect_conflicts(self, evidence: List[Dict[str, Any]]) -> bool:
        """
        Metric 4 — Deterministic conflict detection via keyword matching.

        Conflict is flagged ONLY when:
          - At least one claim contains a positive-polarity term AND
            a *different* claim contains a negative-polarity term.

        This avoids false positives from normal academic hedging
        language (e.g. "however", "despite", "limited").

        No NLP sentiment analysis. No LLM. Pure keyword matching.
        """
        claims = [
            (e.get("claim", "") + " " + e.get("supporting_sentence", "")).lower()
            for e in evidence
        ]

        has_positive = False
        has_negative = False

        for claim in claims:
            for term in self.POSITIVE_TERMS:
                if term in claim:
                    has_positive = True
                    break

            for term in self.NEGATIVE_TERMS:
                if term in claim:
                    has_negative = True
                    break

        # Conflict: requires explicit mixed polarity across claims
        return has_positive and has_negative

    # ─────────────────────────────────────────────────────────────
    # Formatting
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def format_verification_output(result: Dict[str, Any]) -> str:
        """
        Format verification result for CLI display.

        Args:
            result: Output from verify()

        Returns:
            Formatted string for terminal display.
        """
        confidence = result.get("confidence_score", 0)
        metrics = result.get("metrics", {})
        warnings = result.get("warnings", [])

        output = f"\n{'─'*50}\n"
        output += "🔍 VERIFICATION SUMMARY\n"
        output += f"{'─'*50}\n\n"

        # Confidence with visual indicator
        if confidence >= 0.75:
            indicator = "🟢 HIGH"
        elif confidence >= 0.50:
            indicator = "🟡 MODERATE"
        else:
            indicator = "🔴 LOW"

        output += f"   Confidence Score: {confidence:.2f}  ({indicator})\n\n"

        # Warnings
        if warnings:
            output += "   ⚠ Warnings:\n"
            for w in warnings:
                output += f"     - {w}\n"
            output += "\n"
        else:
            output += "   ✅ No warnings\n\n"

        # Metrics
        output += "   📊 Metrics:\n"
        output += f"     Average Similarity:    {metrics.get('avg_similarity', 0):.4f}\n"
        output += f"     Source Diversity:       {metrics.get('source_diversity', 0)}\n"
        output += f"     Normalized Diversity:   {metrics.get('normalized_source_diversity', 0):.2f}\n"
        output += f"     Evidence Density:       {metrics.get('evidence_density', 0):.4f}\n"
        output += f"     Conflicts Detected:     {'Yes' if metrics.get('conflicts_detected') else 'No'}\n"

        return output

    @staticmethod
    def build_verification_input(
        query: str,
        plan: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the verification input contract from existing pipeline data.

        Maps chunk fields to the verification input schema:
          - claim           → evidence_sentence (or truncated chunk text)
          - supporting_sentence → evidence_sentence
          - similarity_score    → similarity_score
          - paper_id / paper_title / year → direct mapping

        The denominator for evidence density is the *total* number of
        chunks that were available before top-k filtering, NOT the
        number of returned chunks.  Retrievers attach this value as
        ``_total_chunks_searched`` on each result dict.

        Args:
            query: Original user query
            plan: PlannerAgent output (has sub_questions)
            chunks: Retrieved chunks from Stage 3

        Returns:
            Dict conforming to the VerificationAgent input contract.
        """
        evidence_list = []

        for chunk in chunks:
            evidence_sentence = chunk.get("evidence_sentence", "")
            claim_text = evidence_sentence if evidence_sentence else chunk.get("text", "")[:300]

            evidence_list.append({
                "claim": claim_text,
                "supporting_sentence": evidence_sentence,
                "similarity_score": chunk.get("similarity_score", 0),
                "paper_id": chunk.get("paper_id", ""),
                "paper_title": chunk.get("paper_title", "Unknown"),
                "year": chunk.get("paper_year", "N/A"),
            })

        # Use _total_chunks_searched from the retriever when available.
        # This is the full chunk pool size *before* top-k selection so
        # that evidence_density reflects how selective the retrieval was.
        total_pool = 0
        if chunks:
            total_pool = chunks[0].get("_total_chunks_searched", len(chunks))

        return {
            "query": query,
            "sub_questions": plan.get("sub_questions", []),
            "evidence": evidence_list,
            "total_chunks_retrieved": total_pool,
        }
