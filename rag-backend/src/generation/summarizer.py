"""Pipeline Summarizer — evidence-grounded literature-review synthesis (Stage 5).

Takes the full Stage 4 output (grouped answer with claims, evidence,
verification metrics) and sends it to the configured LLM to produce
a professional, clear, publication-grade narrative summary.

The summary is appended to the existing output — it does NOT replace
or modify any Stage 4 content.
"""

from typing import Dict, Any, Optional, List

from src.llm.base import BaseLLM


# ── Prompt template ──────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are writing a literature-review-grade synthesis.

Rules:
- Ground every statement in the provided evidence summary.
- Do not hallucinate or introduce external facts.
- Use concise academic prose.
- Avoid copying raw evidence sentences verbatim.

Required structure in plain text:
1) Topic overview (1 short paragraph)
2) Key approaches across papers (1 short paragraph)
3) Major agreements and differences (1 short paragraph)
4) Overall conclusion (1-2 sentences)

Context:
Query: {query}

Evidence-grounded synthesis draft:
{deterministic_summary}

Produce a refined version with the same factual content.
"""


class PipelineSummarizer:
    """Generates a publication-grade narrative from Stage 4 output.

    Usage::

        from src.llm.factory import get_llm
        llm = get_llm()
        summarizer = PipelineSummarizer(llm)
        summary = summarizer.summarize(grouped_answer, verification_output)
    """

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

    def summarize(
        self,
        grouped_answer: str,
        verification_output: str,
        verification_result: Optional[Dict[str, Any]] = None,
        analysis_data: Optional[Dict[str, Any]] = None,
        query: str = "",
    ) -> str:
        """Produce a professional research summary.

        Args:
            grouped_answer:      The full Stage 4 grouped answer text
                                 (sub-questions, claims, evidence, sources).
            verification_output: The formatted verification summary text
                                 (confidence, metrics, audit).
            verification_result: Optional raw verification dict for extra
                                 context (warnings, audit numbers).

        Returns:
            Formatted summary block ready to append to rag_output.txt.
        """
        deterministic_summary = self._deterministic_literature_summary(
            analysis_data=analysis_data,
            grouped_answer=grouped_answer,
            query=query,
        )

        prompt = _SUMMARY_PROMPT.format(
            query=query,
            deterministic_summary=deterministic_summary,
        )

        try:
            raw = self._llm.generate(prompt)
            summary_text = raw.strip()

            # Detect Groq/LLM error strings leaked as content
            if summary_text.startswith("Error:") or not summary_text:
                summary_text = (
                    "[Summary generation failed: LLM returned an error or empty response]\n"
                    "The pipeline output above contains the full evidence "
                    "and verification metrics for manual review."
                )
        except Exception as e:
            summary_text = (
                f"[Summary generation failed: {e}]\n"
                "The pipeline output above contains the full evidence "
                "and verification metrics for manual review."
            )

        return self._format_summary_block(summary_text, verification_result)

    def _deterministic_literature_summary(
        self,
        analysis_data: Optional[Dict[str, Any]],
        grouped_answer: str,
        query: str,
    ) -> str:
        """Create an evidence-grounded synthesis without relying on LLM inference."""
        if not analysis_data or not analysis_data.get("sub_questions"):
            return (
                f"Overview: For the query '{query}', the system identified multiple evidence-backed points. "
                "Approaches and findings vary by paper, with overall direction inferred from retrieved evidence. "
                "Differences are reported when claims diverge, and consensus is stronger where claims align. "
                "Conclusion: the available evidence is informative but should be interpreted with source context."
            )

        sub_sections = analysis_data.get("sub_questions", [])
        mini_blocks: List[str] = []
        all_units: List[Dict[str, Any]] = []
        conflict_count = 0

        for sub in sub_sections:
            question = sub.get("question", "")
            papers = sub.get("papers", [])
            units = []
            for p in papers:
                units.extend(p.get("evidence_units", []))
            all_units.extend(units)
            conflict_count += len(sub.get("conflicts", []))

            methods = self._dominant_terms(units, category="methods")
            findings = self._dominant_terms(units, category="findings")
            trend = " ".join(self._trend_flags(units))

            line = (
                f"Sub-question '{question}': dominant methods include {methods}; "
                f"key findings emphasize {findings}. {trend}".strip()
            )
            mini_blocks.append(line)

        methods_global = self._dominant_terms(all_units, category="methods")
        findings_global = self._dominant_terms(all_units, category="findings")
        differences = (
            "Evidence includes meaningful cross-paper differences"
            if conflict_count > 0
            else "Evidence is mostly directionally aligned across papers"
        )

        overview = (
            f"Overview: For '{query}', the collected evidence spans {len(sub_sections)} sub-questions "
            f"and {len(analysis_data.get('references', []))} papers."
        )
        approaches = f"Key approaches: papers most frequently discuss {methods_global}."
        agreements = f"Agreements and differences: common findings highlight {findings_global}; {differences.lower()}."
        conclusion = (
            "Overall conclusion: the literature indicates a consistent methodological progression with topic-specific "
            "variation in reported outcomes."
        )

        full = "\n".join(mini_blocks + [overview, approaches, agreements, conclusion])
        return full

    @staticmethod
    def _dominant_terms(units: List[Dict[str, Any]], category: str = "methods") -> str:
        if not units:
            return "limited evidence"
        text = " ".join([(u.get("claim") or "") + " " + (u.get("text") or "") for u in units]).lower()
        if category == "methods":
            candidates = ["cnn", "deep learning", "neural", "otsu", "threshold", "morphological", "segmentation"]
        else:
            candidates = ["accuracy", "performance", "robust", "challenge", "limitation", "automation", "detection"]

        hits = [c for c in candidates if c in text]
        if not hits:
            return "mixed methodological evidence"
        return ", ".join(hits[:3])

    @staticmethod
    def _trend_flags(units: List[Dict[str, Any]]) -> List[str]:
        text = " ".join([(u.get("claim") or "") + " " + (u.get("text") or "") for u in units]).lower()
        has_deep = any(k in text for k in ["cnn", "deep learning", "neural", "resnet", "unet"])
        has_classical = any(k in text for k in ["otsu", "threshold", "morphological", "color space", "hsv", "rgb"])
        if has_deep and has_classical:
            return ["A trend from classical image processing toward deep learning is visible."]
        if has_deep:
            return ["Recent evidence is dominated by deep-learning-based approaches."]
        if has_classical:
            return ["Classical image-processing approaches remain prominent in the selected evidence."]
        return ["No single approach family clearly dominates across all evidence units."]

    # ─────────────────────────────────────────────────────────────
    # Formatting
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _format_summary_block(
        summary_text: str,
        verification_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Wrap the LLM summary in a presentable output block."""
        lines = [
            "",
            "=" * 80,
            "📝 RESEARCH SUMMARY",
            "=" * 80,
            "",
            summary_text,
            "",
        ]

        # Append a brief confidence footer if result is available
        if verification_result:
            score = verification_result.get("confidence_score", 0)
            if score >= 0.75:
                level = "HIGH"
            elif score >= 0.50:
                level = "MODERATE"
            else:
                level = "LOW"
            lines.append(f"── Pipeline Confidence: {score:.2f} ({level}) ──")
            lines.append("")

        return "\n".join(lines)
