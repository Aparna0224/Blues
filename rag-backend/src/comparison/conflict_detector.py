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
    TOPIC_SIMILARITY_THRESHOLD = 0.35
    CLAIM_SIMILARITY_THRESHOLD = 0.65

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
    def _has_incompatible_result(cls, a_text: str, b_text: str) -> bool:
        a = (a_text or "").lower()
        b = (b_text or "").lower()
        opposite_pairs = [
            ("higher", "lower"),
            ("increase", "decrease"),
            ("outperform", "underperform"),
            ("effective", "ineffective"),
            ("improved", "worse"),
        ]
        for left, right in opposite_pairs:
            if (left in a and right in b) or (right in a and left in b):
                return True
        return False

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
            polarity_conflict = cls._has_polarity_conflict(a_claim, b_claim)
            incompatible = cls._has_incompatible_result(a_claim, b_claim)

            # Required conflict rule: similar topic but divergent claim.
            if topic_similarity <= cls.TOPIC_SIMILARITY_THRESHOLD:
                continue
            if not polarity_conflict and not incompatible and claim_similarity >= cls.CLAIM_SIMILARITY_THRESHOLD:
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
                    f"but diverge in claims (claim_similarity={claim_similarity:.2f}); "
                    f"this indicates incompatible interpretation of similar evidence."
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
    def no_conflict_explanation(cls, units: List[Dict[str, Any]]) -> str:
        if not units:
            return "No conflicts detected because no comparable cross-paper claims were available."

        section_groups: Dict[str, int] = {}
        for u in units:
            sec = str(u.get("section", "unknown") or "unknown")
            section_groups[sec] = section_groups.get(sec, 0) + 1

        if len(section_groups) > 1:
            sections = ", ".join(sorted(section_groups.keys())[:4])
            return (
                "No conflicts detected because the compared claims primarily address different aspects of the problem "
                f"across sections ({sections}) rather than reporting incompatible outcomes."
            )

        return (
            "No conflicts detected because cross-paper claims are directionally aligned on overlapping topics and "
            "do not present incompatible results."
        )

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

        deep_terms = {"cnn", "deep", "neural", "transformer", "resnet", "unet", "u-net", "bert"}
        classical_terms = {"threshold", "otsu", "morphological", "watershed", "color", "hsv", "cmyk", "rgb", "rule-based"}
        manual_terms = {"manual", "microscopy", "expert", "visual"}

        method_groups: Dict[str, List[int]] = {
            "deep learning": [],
            "rule-based image processing": [],
            "manual analysis": [],
            "hybrid or unspecified computational methods": [],
        }
        for i, unit in enumerate(units):
            text = f"{unit.get('claim', '')} {unit.get('text', '')}".lower()
            has_deep = any(t in text for t in deep_terms)
            has_classical = any(t in text for t in classical_terms)
            has_manual = any(t in text for t in manual_terms)

            if has_manual and not has_deep and not has_classical:
                method_groups["manual analysis"].append(i)
            elif has_deep and not has_classical:
                method_groups["deep learning"].append(i)
            elif has_classical and not has_deep:
                method_groups["rule-based image processing"].append(i)
            else:
                method_groups["hybrid or unspecified computational methods"].append(i)

        non_empty = {k: v for k, v in method_groups.items() if v}
        ordered = sorted(non_empty.items(), key=lambda kv: len(kv[1]), reverse=True)

        approach_lines = []
        for name, ids in ordered[:3]:
            purpose = "to automate detection and improve reproducibility"
            sample_text = " ".join((units[idx].get("claim") or units[idx].get("text") or "") for idx in ids[:2]).lower()
            if any(t in sample_text for t in ["segment", "segmentation", "delineat"]):
                purpose = "to segment and delineate relevant structures"
            elif any(t in sample_text for t in ["classif", "predict", "label"]):
                purpose = "to classify outcomes from extracted features"
            elif any(t in sample_text for t in ["screen", "diagnos", "triage"]):
                purpose = "to support screening and diagnostic workflows"
            if name == "hybrid or unspecified computational methods":
                approach_lines.append(f"hybrid or unspecified computational pipelines are used {purpose}")
            else:
                approach_lines.append(f"{name} methods are used {purpose}")

        conflicts = cls.detect_conflicts(units)
        if conflicts:
            difference_text = (
                "Papers diverge where comparable claims report incompatible outcomes or opposite effectiveness "
                "under similar topical conditions"
            )
        else:
            difference_text = cls.no_conflict_explanation(units)

        if method_groups["deep learning"] and method_groups["rule-based image processing"]:
            trend_text = "The evidence indicates an ongoing shift from handcrafted rule-based pipelines toward learned models in recent studies"
        elif method_groups["deep learning"]:
            trend_text = "Recent evidence emphasizes learned models as the primary implementation strategy"
        elif method_groups["rule-based image processing"]:
            trend_text = "Classical image-processing pipelines remain central in the currently retrieved literature"
        elif method_groups["manual analysis"]:
            trend_text = "Manual analytical procedures remain a reference baseline for interpretation and validation"
        else:
            trend_text = "The retrieved evidence emphasizes implementation details more than temporal methodological shifts"

        paragraph = (
            f"Across the selected papers, {'; '.join(approach_lines)}. "
            f"These approaches differ in how they trade off interpretability, annotation demand, and robustness to dataset variability. "
            f"{difference_text}. {trend_text}."
        )

        support_indices = sorted({idx for ids in non_empty.values() for idx in ids})[:8]
        return {
            "paragraph": paragraph,
            "support_indices": support_indices,
        }
