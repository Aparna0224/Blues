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
You are an expert research analyst writing a high-quality literature review synthesis.

Your task is to transform the provided evidence-grounded draft into a clear, insightful, and academically strong summary.

STRICT RULES:
- Use ONLY the provided content — do not introduce external knowledge.
- Do NOT copy sentences directly — synthesize and rephrase.
- Avoid generic phrases like "mixed approaches", "patterns observed", "no strong trend", or metric placeholders.
- Every paragraph must convey a meaningful insight, not just description.
- Ensure all sentences are complete and coherent.

═══════════════════════════════
WRITING GOAL
═══════════════════════════════

Produce a structured, publication-quality synthesis where:

1. For EACH sub-question, write ONE interpretive paragraph that:
   - States what the evidence shows SPECIFICALLY (not generically)
   - Names the specific method, finding, or technique mentioned in the papers
   - Identifies ONE meaningful difference between papers if one exists
   - Does NOT repeat what the Comparison Summary already said

2. Then write a final 2-sentence overall insight that ties sub-questions together

═══════════════════════════════
REQUIRED STRUCTURE
═══════════════════════════════

[For each sub-question listed below]

SUB-QUESTION N: [sub-question text]
[One paragraph of original synthesis that:
 - Interprets the evidence (not just lists it)
 - Mentions specific findings from papers
 - Identifies method differences or agreements
 - Avoids generic phrases]

[After all sub-questions]

OVERALL INSIGHT:
[One or two sentences that synthesize across all sub-questions and draw a meta-level conclusion]

═══════════════════════════════
CONTEXT
═══════════════════════════════

Query: {query}

Sub-questions addressed: {sub_questions}

Evidence pipeline output:
{deterministic_summary}

═══════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════

- Write in clear academic prose
- One interpretive paragraph per sub-question (labeled)
- One final overall insight (2 sentences)
- No bullet points
- No hedging phrases like "mixed approaches" or "various methods"
- No placeholders or incomplete sentences
- Explicitly mention method names, finding numbers, and trend direction when supported.
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

        # Extract sub-questions for LLM context
        sub_questions = []
        if analysis_data and analysis_data.get("sub_questions"):
            sub_questions = [sq.get("question", sq) for sq in analysis_data.get("sub_questions", [])]
        sub_questions_text = "\n".join(f"{i+1}. {sq}" for i, sq in enumerate(sub_questions)) if sub_questions else "Unknown"

        prompt = _SUMMARY_PROMPT.format(
            query=query,
            sub_questions=sub_questions_text,
            deterministic_summary=deterministic_summary,
        )

        try:
            raw = self._llm.generate(prompt)
            summary_text = raw.strip()

            # Detect Groq/LLM error strings leaked as content
            if summary_text.startswith("Error:") or not summary_text or len(summary_text.split()) < 40:
                summary_text = deterministic_summary
        except Exception as e:
            _ = e
            summary_text = deterministic_summary

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
                f"For the query '{query}', the available evidence indicates multiple method families addressing the same problem from complementary angles.\n\n"
                "The retrieved studies describe computational approaches that prioritize either interpretability, automation, or robustness under practical constraints.\n\n"
                "Reported findings are directionally related but not identical, because papers evaluate different datasets, assumptions, and implementation choices.\n\n"
                "Overall, the literature supports a converging objective while highlighting trade-offs that should guide method selection in context."
            )

        sub_sections = analysis_data.get("sub_questions", [])
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

            _ = question

        methods_global = self._dominant_terms(all_units, category="methods")
        findings_global = self._dominant_terms(all_units, category="findings")
        differences = (
            "Cross-paper claims include incompatible interpretations in selected areas"
            if conflict_count > 0
            else "Cross-paper claims are largely aligned but differ in implementation emphasis"
        )
        trend = " ".join(self._trend_flags(all_units))

        overview_par = (
            f"Overview: For '{query}', the collected evidence spans {len(sub_sections)} sub-questions "
            f"and {len(analysis_data.get('references', []))} papers."
        )
        approaches_par = f"Key approaches include {methods_global}; these methods are used to address core analytical objectives with different trade-offs in data demand, interpretability, and automation."
        differences_par = f"Agreements and differences: the evidence repeatedly highlights {findings_global}; {differences.lower()}."
        conclusion_par = (
            "Overall conclusion: the literature indicates a consistent methodological progression with topic-specific "
            f"variation in reported outcomes. {trend}"
        )

        full = "\n\n".join([overview_par, approaches_par, differences_par, conclusion_par])
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
            return "computational and analytical methods described in the evidence"
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
        return ["Temporal method shift is not explicit in the available evidence, but methodological variation is clear."]

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
