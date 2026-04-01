"""Conflict detection and comparison summary for evidence units.

Provides explainable cross-paper conflict detection for Stage 4/5 outputs.
The detector is intentionally deterministic and transparent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set
from itertools import combinations


class ConflictDetector:
    """Detect and explain cross-paper conflicts between evidence units."""

    POSITIVE_TERMS: Set[str] = {
        "improves", "improved", "increase", "increases", "effective", "benefit",
        "outperform", "outperforms", "reliable", "reduces", "safer",
    }
    NEGATIVE_TERMS: Set[str] = {
        "fails", "failed", "does not", "cannot", "ineffective", "no benefit",
        "underperform", "underperforms", "worse", "limited", "harmful",
    }

    METHOD_TERMS: Set[str] = {"method", "methodology", "approach", "pipeline", "framework"}
    RESULT_TERMS: Set[str] = {"result", "results", "experiment", "evaluation", "performance"}
    TOPIC_SIMILARITY_THRESHOLD = 0.70
    CLAIM_SIMILARITY_THRESHOLD = 0.50

    @classmethod
    def _tokenize(cls, text: str) -> Set[str]:
        if not text:
            return set()
        cleaned = (
            text.lower()
            .replace("\n", " ")
            .replace(".", " ")
            .replace(",", " ")
            .replace(";", " ")
            .replace(":", " ")
            .replace("(", " ")
            .replace(")", " ")
            .replace("[", " ")
            .replace("]", " ")
            .replace("\"", " ")
            .replace("'", " ")
        )
        words = [w.strip() for w in cleaned.split() if len(w.strip()) > 2]
        return set(words)

    @classmethod
    def _concept_overlap(cls, a_text: str, b_text: str) -> float:
        a = cls._tokenize(a_text)
        b = cls._tokenize(b_text)
        if not a or not b:
            return 0.0
        inter = len(a.intersection(b))
        return (2 * inter) / (len(a) + len(b)) if (len(a) + len(b)) else 0.0

    @classmethod
    def _has_polarity_conflict(cls, a_text: str, b_text: str) -> bool:
        a_lower = (a_text or "").lower()
        b_lower = (b_text or "").lower()
        a_pos = any(t in a_lower for t in cls.POSITIVE_TERMS)
        a_neg = any(t in a_lower for t in cls.NEGATIVE_TERMS)
        b_pos = any(t in b_lower for t in cls.POSITIVE_TERMS)
        b_neg = any(t in b_lower for t in cls.NEGATIVE_TERMS)
        return (a_pos and b_neg) or (a_neg and b_pos)

    @classmethod
    def _classify_type(cls, section_a: str, section_b: str) -> str:
        sa = (section_a or "").lower()
        sb = (section_b or "").lower()
        if any(t in sa for t in cls.METHOD_TERMS) or any(t in sb for t in cls.METHOD_TERMS):
            return "Methodological"
        if any(t in sa for t in cls.RESULT_TERMS) or any(t in sb for t in cls.RESULT_TERMS):
            return "Empirical"
        return "Conceptual"

    @classmethod
    def _topic_similarity(cls, a: Dict[str, Any], b: Dict[str, Any]) -> float:
        """Compute concept overlap similarity between two evidence units."""
        a_text = " ".join([
            str(a.get("claim", "")),
            str(a.get("text", "")),
        ])
        b_text = " ".join([
            str(b.get("claim", "")),
            str(b.get("text", "")),
        ])
        return cls._concept_overlap(a_text, b_text)

    @classmethod
    def _claim_similarity(cls, a_claim: str, b_claim: str) -> float:
        """Compute claim similarity adjusted for polarity opposition."""
        overlap = cls._concept_overlap(a_claim, b_claim)
        if cls._has_polarity_conflict(a_claim, b_claim):
            # Opposing polarity on similar concepts should lower claim similarity.
            return max(0.0, 1.0 - overlap)
        return overlap

    @classmethod
    def detect_conflicts(cls, units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Pairwise conflict detection over evidence units."""
        conflicts: List[Dict[str, Any]] = []
        if len(units) < 2:
            return conflicts

        for i, j in combinations(range(len(units)), 2):
            a = units[i]
            b = units[j]
            if not a.get("paper_id") or a.get("paper_id") == b.get("paper_id"):
                continue

            a_claim = a.get("claim") or a.get("text") or ""
            b_claim = b.get("claim") or b.get("text") or ""

            topic_similarity = cls._topic_similarity(a, b)
            claim_similarity = cls._claim_similarity(a_claim, b_claim)

            # Required conflict rule: similar topic but divergent claim.
            if topic_similarity <= cls.TOPIC_SIMILARITY_THRESHOLD:
                continue
            if claim_similarity >= cls.CLAIM_SIMILARITY_THRESHOLD:
                continue

            conflict_type = cls._classify_type(a.get("section", ""), b.get("section", ""))
            strength = max(0.0, min(1.0, (topic_similarity - claim_similarity + 1.0) / 2.0))

            conflicts.append({
                "a": a,
                "b": b,
                "type": conflict_type,
                "strength": strength,
                "topic_similarity": topic_similarity,
                "claim_similarity": claim_similarity,
                "explanation": (
                    f"Both papers discuss overlapping concepts (topic_similarity={topic_similarity:.2f}) "
                    f"but diverge in claims (claim_similarity={claim_similarity:.2f})."
                ),
                "pair": (i, j),
            })

        conflicts.sort(key=lambda c: c.get("strength", 0.0), reverse=True)
        return conflicts

    @classmethod
    def comparison_summary(
        cls,
        units: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Cluster evidence by concept overlap and compute consensus metrics."""
        if not units:
            return {
                "supporting_clusters": 0,
                "conflicting_clusters": 0,
                "consensus_level": "Low",
            }

        clusters: List[List[int]] = []
        for idx, unit in enumerate(units):
            placed = False
            u_text = unit.get("claim") or unit.get("text") or ""
            for cluster in clusters:
                anchor = units[cluster[0]]
                a_text = anchor.get("claim") or anchor.get("text") or ""
                if cls._concept_overlap(u_text, a_text) >= 0.30:
                    cluster.append(idx)
                    placed = True
                    break
            if not placed:
                clusters.append([idx])

        conflicting_cluster_ids: Set[int] = set()
        for c in conflicts:
            i, j = c.get("pair", (-1, -1))
            for cid, cluster in enumerate(clusters):
                if i in cluster or j in cluster:
                    conflicting_cluster_ids.add(cid)

        supporting_clusters = len(clusters)
        conflicting_clusters = len(conflicting_cluster_ids)

        if conflicting_clusters == 0:
            consensus = "High"
        elif conflicting_clusters <= max(1, supporting_clusters // 2):
            consensus = "Medium"
        else:
            consensus = "Low"

        return {
            "supporting_clusters": supporting_clusters,
            "conflicting_clusters": conflicting_clusters,
            "consensus_level": consensus,
        }

    @classmethod
    def grounded_comparison_statements(
        cls,
        units: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build evidence-grounded comparison statements with explicit unit support."""
        if not units:
            return []

        by_section: Dict[str, List[int]] = {}
        for idx, unit in enumerate(units):
            section = str(unit.get("section", "unknown") or "unknown")
            by_section.setdefault(section, []).append(idx)

        statements: List[Dict[str, Any]] = []
        for section, indices in sorted(by_section.items(), key=lambda kv: len(kv[1]), reverse=True):
            if not indices:
                continue
            example_unit = units[indices[0]]
            statements.append({
                "text": (
                    f"Evidence in {section} emphasizes themes similar to "
                    f"'{(example_unit.get('claim') or example_unit.get('text') or '')[:90]}...'."
                ),
                "support_indices": indices,
            })

        return statements

    @classmethod
    def generate_literature_comparison(cls, units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a grounded comparison paragraph describing approaches, agreements, and trends."""
        if not units:
            return {
                "paragraph": "No cross-paper comparison can be formed due to insufficient evidence units.",
                "support_indices": [],
            }

        deep_terms = {"cnn", "deep", "neural", "transformer", "resnet", "unet", "u-net"}
        classical_terms = {"threshold", "otsu", "morphological", "watershed", "color", "hsv", "cmyk", "rgb"}

        deep_ids: List[int] = []
        classical_ids: List[int] = []
        mixed_ids: List[int] = []
        for i, unit in enumerate(units):
            text = f"{unit.get('claim', '')} {unit.get('text', '')}".lower()
            has_deep = any(t in text for t in deep_terms)
            has_classical = any(t in text for t in classical_terms)
            if has_deep and not has_classical:
                deep_ids.append(i)
            elif has_classical and not has_deep:
                classical_ids.append(i)
            else:
                mixed_ids.append(i)

        # Agreement signal from high-overlap claim pairs.
        agreements = 0
        for i, j in combinations(range(len(units)), 2):
            if units[i].get("paper_id") == units[j].get("paper_id"):
                continue
            c1 = units[i].get("claim") or units[i].get("text") or ""
            c2 = units[j].get("claim") or units[j].get("text") or ""
            if cls._concept_overlap(c1, c2) >= 0.45 and cls._claim_similarity(c1, c2) >= 0.50:
                agreements += 1

        dominant = "mixed approaches"
        dominant_ids = mixed_ids
        if len(deep_ids) > len(classical_ids) and len(deep_ids) >= len(mixed_ids):
            dominant = "deep learning approaches"
            dominant_ids = deep_ids
        elif len(classical_ids) > len(deep_ids) and len(classical_ids) >= len(mixed_ids):
            dominant = "classical image-processing approaches"
            dominant_ids = classical_ids

        trends_text = (
            "A trend from color-space/thresholding pipelines toward deep learning models is visible"
            if deep_ids and classical_ids
            else "The available evidence does not show a strong transition trend across approach families"
        )

        paragraph = (
            f"Across the selected papers, the dominant pattern is {dominant}. "
            f"Several studies agree on core segmentation goals and report directionally similar claims "
            f"({agreements} cross-paper agreement links detected). "
            f"At the same time, differences appear in implementation details and reported outcomes across papers. "
            f"{trends_text}."
        )

        support_indices = sorted(set(dominant_ids + deep_ids + classical_ids + mixed_ids))[:8]
        return {
            "paragraph": paragraph,
            "support_indices": support_indices,
        }
