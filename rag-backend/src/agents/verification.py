"""Verification Agent for Stage 4 — Deterministic reliability estimation (v2).

Evaluates the reliability of evidence-backed answers using:
  - Claim relevance filtering  (reject generic/motivational sentences)
  - Claim deduplication         (remove repeated evidence)
  - Similarity threshold gating (ignore weak matches from scoring)
  - Average similarity score    (across strong claims only)
  - Evidence density            (relevant_claims / top_k_returned)
  - Source diversity             (normalised unique-paper count)
  - Cross-paper conflict detection

Produces a deterministic confidence score with structured warnings
and a full filtering-pipeline audit log.

MUST NOT:
  - Call database or LLM
  - Re-embed or re-rank text
  - Modify the answer
  - Call any external service
"""

from typing import List, Dict, Any, Tuple


class VerificationAgent:
    """
    Deterministic post-answer verification agent (v2).

    Receives structured evidence from the answer-generation step and
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
          "total_chunks_retrieved": 15
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
          "warnings": [...],
          "audit": {
            "total_claims_received": 15,
            "claims_after_dedup": 12,
            "claims_after_relevance_filter": 10,
            "claims_above_similarity_threshold": 9,
            "claims_used_for_scoring": 9,
            "claims_rejected": 6
          }
        }
    """

    # ── Confidence formula weights ───────────────────────────────
    WEIGHT_SIMILARITY = 0.5
    WEIGHT_DIVERSITY = 0.3
    WEIGHT_DENSITY = 0.2

    # ── Source diversity normalisation cap ────────────────────────
    DIVERSITY_CAP = 5

    # ── Similarity threshold — claims below this are excluded
    #    from the confidence computation (still counted in audit) ──
    SIMILARITY_THRESHOLD = 0.70

    # ── Claim-relevance keyword lists ────────────────────────────
    #    A claim is "relevant" if it contains at least one of these
    #    domain terms.  Claims that contain *none* are treated as
    #    generic/motivational and excluded from scoring.
    RELEVANCE_TERMS = [
        # Method / technique terms
        "method", "technique", "approach", "model", "algorithm",
        "framework", "architecture", "pipeline", "system", "tool",
        # XAI-specific terms
        "saliency", "attention", "shap", "lime", "grad-cam",
        "feature attribution", "counterfactual", "prototype",
        "interpretability", "interpretable", "explainability",
        "explainable", "explanation", "transparent", "transparency",
        # ML / DL terms
        "neural network", "deep learning", "machine learning",
        "classification", "prediction", "training", "inference",
        "transformer", "convolutional", "cnn", "rnn", "lstm",
        "transfer learning", "fine-tuning", "pre-trained",
        # Medical / domain terms
        "diagnosis", "diagnostic", "clinical", "patient",
        "medical imaging", "radiology", "pathology", "prognosis",
        "treatment", "disease", "imaging", "x-ray", "mri", "ct scan",
        # Evaluation terms
        "accuracy", "performance", "evaluation", "benchmark",
        "recall", "precision", "f1", "auc", "sensitivity",
        "specificity", "robustness",
    ]

    # ── Conflict detection — strong, unambiguous phrases only ────
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
    WEAK_SIMILARITY_MULTIPLIER = 0.7   # applied when avg_sim < 0.65

    # ── Deduplication threshold ──────────────────────────────────
    DEDUP_CHAR_OVERLAP = 0.85  # 85 % character overlap → duplicate

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def verify(self, verification_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run deterministic verification on structured evidence.

        Pipeline:
          1. Deduplicate claims
          2. Filter by claim relevance (domain keywords)
          3. Gate by similarity threshold
          4. Compute metrics on surviving claims
          5. Apply edge-case penalties
          6. Build audit log

        Args:
            verification_input: Dict following the input contract.

        Returns:
            Dict following the output contract.
        """
        raw_evidence = verification_input.get("evidence", [])
        total_chunks = verification_input.get("total_chunks_retrieved", 0)

        total_received = len(raw_evidence)

        # ── Case A: No evidence at all ───────────────────────────
        if not raw_evidence:
            return self._empty_result(total_received)

        # ── Step 1: Deduplicate ──────────────────────────────────
        deduped = self._deduplicate_claims(raw_evidence)
        after_dedup = len(deduped)

        # ── Step 2: Relevance filter ─────────────────────────────
        relevant = self._filter_relevant_claims(deduped)
        after_relevance = len(relevant)

        # If all claims were filtered, fall back to deduped set
        # so we still produce *some* output.
        scoring_base = relevant if relevant else deduped

        # ── Step 3: Similarity gating ────────────────────────────
        strong = [
            e for e in scoring_base
            if e.get("similarity_score", 0) >= self.SIMILARITY_THRESHOLD
        ]
        after_sim_gate = len(strong)

        # Fall back to scoring_base if nothing passes threshold
        scoring_set = strong if strong else scoring_base

        claims_used = len(scoring_set)
        claims_rejected = total_received - claims_used

        # ── Step 4: Compute metrics on scoring_set ───────────────
        avg_similarity = self._compute_avg_similarity(scoring_set)
        source_diversity, norm_diversity = self._compute_source_diversity(
            scoring_set
        )
        evidence_density = self._compute_evidence_density(
            scoring_set, total_chunks
        )
        conflicts_detected = self._detect_conflicts(scoring_set)

        # ── Step 5: Base confidence ──────────────────────────────
        confidence = (
            self.WEIGHT_SIMILARITY * avg_similarity
            + self.WEIGHT_DIVERSITY * norm_diversity
            + self.WEIGHT_DENSITY * evidence_density
        )

        # ── Step 6: Edge-case penalties & calibration ────────────
        warnings: List[str] = []

        # Single source
        if source_diversity == 1:
            confidence -= self.SINGLE_SOURCE_PENALTY
            warnings.append("Low source diversity")

        # All evidence weakly related (even in scoring_set)
        max_sim = max(
            (e.get("similarity_score", 0) for e in scoring_set), default=0
        )
        if max_sim < 0.60:
            confidence = min(confidence, 0.5)
            warnings.append("All evidence weakly related")

        # Conflict
        if conflicts_detected:
            confidence -= self.CONFLICT_PENALTY
            warnings.append("Mixed findings across sources")

        # Weak average similarity calibration
        if avg_similarity < 0.65:
            confidence *= self.WEAK_SIMILARITY_MULTIPLIER
            if "All evidence weakly related" not in warnings:
                warnings.append("Weak evidence strength")

        # Threshold-based warnings
        if source_diversity < 2 and "Low source diversity" not in warnings:
            warnings.append("Low source diversity")

        if evidence_density < 0.3:
            warnings.append("Sparse evidence coverage")

        if after_relevance == 0:
            warnings.append("No domain-relevant claims found")

        # Clamp
        confidence = max(0.0, min(confidence, 1.0))

        # ── Build result ─────────────────────────────────────────
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
            "audit": {
                "total_claims_received": total_received,
                "claims_after_dedup": after_dedup,
                "claims_after_relevance_filter": after_relevance,
                "claims_above_similarity_threshold": after_sim_gate,
                "claims_used_for_scoring": claims_used,
                "claims_rejected": claims_rejected,
            },
        }

    # ─────────────────────────────────────────────────────────────
    # Filtering helpers
    # ─────────────────────────────────────────────────────────────

    def _deduplicate_claims(
        self, evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate or near-duplicate claims.

        Two claims are duplicates if their normalised text shares
        >= DEDUP_CHAR_OVERLAP fraction of characters.  When a
        duplicate is found the copy with the higher similarity
        score is kept.
        """
        if not evidence:
            return evidence

        kept: List[Dict[str, Any]] = []

        for item in evidence:
            text = self._normalise_text(
                item.get("claim", "") + item.get("supporting_sentence", "")
            )
            is_dup = False
            for i, existing in enumerate(kept):
                existing_text = self._normalise_text(
                    existing.get("claim", "")
                    + existing.get("supporting_sentence", "")
                )
                overlap = self._char_overlap(text, existing_text)
                if overlap >= self.DEDUP_CHAR_OVERLAP:
                    is_dup = True
                    # Keep the one with higher similarity
                    if item.get("similarity_score", 0) > existing.get(
                        "similarity_score", 0
                    ):
                        kept[i] = item
                    break
            if not is_dup:
                kept.append(item)

        return kept

    def _filter_relevant_claims(
        self, evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Keep only claims that contain at least one domain-relevant term.

        This removes generic motivational statements like
        "legal and privacy aspects are rising" that do not describe
        an approach, method, or finding.
        """
        relevant = []
        for item in evidence:
            text = (
                item.get("claim", "")
                + " "
                + item.get("supporting_sentence", "")
            ).lower()
            if any(term in text for term in self.RELEVANCE_TERMS):
                relevant.append(item)
        return relevant

    # ─────────────────────────────────────────────────────────────
    # Metric computations
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_avg_similarity(evidence: List[Dict[str, Any]]) -> float:
        """Metric 1 — Average similarity score across claims."""
        scores = [e.get("similarity_score", 0) for e in evidence]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def _compute_source_diversity(
        self, evidence: List[Dict[str, Any]]
    ) -> Tuple[int, float]:
        """
        Metric 2 — Source diversity (unique papers).

        Returns:
            (unique_sources, normalised_diversity)
        """
        paper_ids = [
            e.get("paper_id", "") for e in evidence if e.get("paper_id")
        ]
        unique_sources = len(set(paper_ids))
        normalised = min(unique_sources / self.DIVERSITY_CAP, 1.0)
        return unique_sources, normalised

    @staticmethod
    def _compute_evidence_density(
        evidence: List[Dict[str, Any]], total_chunks: int
    ) -> float:
        """
        Metric 3 — Evidence density.

        Defined as:  relevant_claims / total_chunks_retrieved

        ``total_chunks`` is the top-k chunks returned by the
        retriever.  This gives a realistic 0-1 range reflecting
        how many returned chunks actually contributed useful
        evidence after filtering.
        """
        if total_chunks == 0:
            return 0.0
        return min(len(evidence) / total_chunks, 1.0)

    def _detect_conflicts(self, evidence: List[Dict[str, Any]]) -> bool:
        """
        Metric 4 — Cross-paper conflict detection.

        Conflict is flagged ONLY when:
          - A claim from paper_A contains a positive-polarity term AND
          - A claim from a *different* paper_B contains a negative term.

        Same-paper contrast is normal academic nuance and is ignored.
        """
        positive_papers: set = set()
        negative_papers: set = set()

        for item in evidence:
            text = (
                item.get("claim", "")
                + " "
                + item.get("supporting_sentence", "")
            ).lower()
            pid = item.get("paper_id", "")

            for term in self.POSITIVE_TERMS:
                if term in text:
                    positive_papers.add(pid)
                    break

            for term in self.NEGATIVE_TERMS:
                if term in text:
                    negative_papers.add(pid)
                    break

        # Conflict only if polarity spans different papers
        if not positive_papers or not negative_papers:
            return False
        # True if there are positive-only and negative-only papers
        return bool(positive_papers - negative_papers) or bool(
            negative_papers - positive_papers
        )

    # ─────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_text(text: str) -> str:
        """Lower-case, strip, collapse whitespace."""
        return " ".join(text.lower().split())

    @staticmethod
    def _char_overlap(a: str, b: str) -> float:
        """Word-level Jaccard overlap ratio.

        Uses word tokens (not individual characters) so that
        claims with different words but overlapping letters
        are correctly treated as distinct.
        """
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        set_a = set(a.split())
        set_b = set(b.split())
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return intersection / union

    @staticmethod
    def _empty_result(total_received: int) -> Dict[str, Any]:
        """Return the canonical empty-evidence result."""
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
            "audit": {
                "total_claims_received": total_received,
                "claims_after_dedup": 0,
                "claims_after_relevance_filter": 0,
                "claims_above_similarity_threshold": 0,
                "claims_used_for_scoring": 0,
                "claims_rejected": total_received,
            },
        }

    # ─────────────────────────────────────────────────────────────
    # Formatting
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def format_verification_output(result: Dict[str, Any]) -> str:
        """
        Format verification result for CLI display.

        Includes confidence score, warnings, metrics, and full
        filtering-pipeline audit log.

        Args:
            result: Output from verify()

        Returns:
            Formatted string for terminal display.
        """
        confidence = result.get("confidence_score", 0)
        metrics = result.get("metrics", {})
        warnings = result.get("warnings", [])
        audit = result.get("audit", {})

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

        # Audit log
        if audit:
            output += "\n   📋 Audit:\n"
            output += f"     Claims Received:          {audit.get('total_claims_received', 0)}\n"
            output += f"     After Deduplication:       {audit.get('claims_after_dedup', 0)}\n"
            output += f"     After Relevance Filter:    {audit.get('claims_after_relevance_filter', 0)}\n"
            output += f"     Above Similarity ≥0.70:    {audit.get('claims_above_similarity_threshold', 0)}\n"
            output += f"     Used for Scoring:          {audit.get('claims_used_for_scoring', 0)}\n"
            output += f"     Rejected:                  {audit.get('claims_rejected', 0)}\n"

        return output

    @staticmethod
    def build_verification_input(
        query: str,
        plan: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the verification input contract from pipeline data.

        Maps chunk fields to the verification input schema.

        The denominator for evidence density is ``len(chunks)``
        — i.e. the top-k results actually returned by the retriever.
        This gives a realistic 0-1 density range.

        Args:
            query:  Original user query
            plan:   PlannerAgent output (has sub_questions)
            chunks: Retrieved chunks from Stage 3

        Returns:
            Dict conforming to the VerificationAgent input contract.
        """
        evidence_list = []

        for chunk in chunks:
            evidence_sentence = chunk.get("evidence_sentence", "")
            claim_text = (
                evidence_sentence if evidence_sentence
                else chunk.get("text", "")[:300]
            )

            evidence_list.append({
                "claim": claim_text,
                "supporting_sentence": evidence_sentence,
                "similarity_score": chunk.get("similarity_score", 0),
                "paper_id": chunk.get("paper_id", ""),
                "paper_title": chunk.get("paper_title", "Unknown"),
                "year": chunk.get("paper_year", "N/A"),
            })

        return {
            "query": query,
            "sub_questions": plan.get("sub_questions", []),
            "evidence": evidence_list,
            "total_chunks_retrieved": len(chunks),
        }
