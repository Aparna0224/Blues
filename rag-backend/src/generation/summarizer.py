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
You are a senior research analyst synthesising findings from multiple
academic papers.  The user asked a research question and our pipeline
retrieved evidence — including claims from Introduction, Methodology,
Results, Discussion, and Conclusion sections of the source papers.

Below is the full pipeline output with claims, their source sections,
similarity scores, and verification metrics.

YOUR TASK:
Produce a **structured research summary** that covers:

1. **Key Findings** — What do the results and evidence actually show?
   Cite specific data points, metrics, or outcomes from [Results] or
   [Discussion] claims when available.

2. **Methodological Insights** — How were these findings obtained?
   Mention study designs, datasets, models, or techniques referenced
   in [Methodology] claims.  Keep this brief (1-2 sentences).

3. **Consensus & Conflicts** — Where do the sources agree or
   disagree?  If the verification detected conflicts, explain them.

4. **Limitations & Confidence** — Note any caveats, small sample
   sizes, or weak evidence.  Use the verification confidence score
   to frame overall reliability.

STYLE RULES:
- Write in flowing paragraphs (2-4 sentences each).  NO bullet
  points, numbered lists, or section headers.
- Use natural citations: "Zhang et al. (2022) found that ..." or
  "A recent study demonstrated ...".
- Lead with the most important findings, not background.
- Be specific: prefer "accuracy improved from 78% to 91%" over
  "accuracy improved significantly".
- If evidence comes from methodology or results sections, say so
  naturally: "Using a transformer-based approach, ..." or
  "Experimental results showed ...".
- Total length: **150-300 words**.
- Do NOT mention pipeline internals (chunks, embeddings, scores).
- Do NOT invent facts beyond what the evidence shows.
- End with a single sentence on confidence and evidence breadth.

─── PIPELINE OUTPUT ───

{pipeline_output}

─── END OF PIPELINE OUTPUT ───

Now write the structured research summary:
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
