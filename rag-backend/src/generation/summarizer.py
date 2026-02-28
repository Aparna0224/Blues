"""Pipeline Summarizer — LLM-generated research summary (Stage 5).

Takes the full Stage 4 output (grouped answer with claims, evidence,
verification metrics) and sends it to the configured LLM to produce
a professional, clear, publication-grade narrative summary.

The summary is appended to the existing output — it does NOT replace
or modify any Stage 4 content.
"""

from typing import Dict, Any, Optional

from src.llm.base import BaseLLM


# ── Prompt template ──────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are a research synthesis assistant.  Below is the output of an
automated Retrieval-Augmented Generation (RAG) pipeline that answered
a research question using evidence extracted from academic papers.

The output contains:
  • Sub-questions and their evidence-backed claims
  • Similarity scores and source papers for each claim
  • A verification summary with confidence metrics

YOUR TASK:
Write a **professional, clear research summary** that synthesizes
all of the findings below into a coherent narrative.

RULES:
1. Write in academic prose — no bullet points, no raw scores.
2. Cite papers by title and year inline (e.g., "Smith et al., 2023").
3. Organize by theme, not by sub-question number.
4. If the verification flagged conflicts, acknowledge both sides.
5. End with a brief statement about the overall confidence level
   and any caveats (low diversity, sparse evidence, etc.).
6. Keep the summary between 200-400 words.
7. Do NOT invent facts — only synthesize what is provided below.

─── PIPELINE OUTPUT ───

{pipeline_output}

─── END OF PIPELINE OUTPUT ───

Write the research summary now:
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
        # Assemble the full pipeline output the LLM will see
        pipeline_output = grouped_answer + "\n" + verification_output

        prompt = _SUMMARY_PROMPT.format(pipeline_output=pipeline_output)

        try:
            raw = self._llm.generate(prompt)
            summary_text = raw.strip()
        except Exception as e:
            summary_text = (
                f"[Summary generation failed: {e}]\n"
                "The pipeline output above contains the full evidence "
                "and verification metrics for manual review."
            )

        return self._format_summary_block(summary_text, verification_result)

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
