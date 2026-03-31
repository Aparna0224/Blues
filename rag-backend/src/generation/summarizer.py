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
You are a knowledgeable research assistant having a conversation with
the user.  They asked a research question and our system retrieved
evidence from academic papers.  Below is the raw pipeline output.

YOUR TASK:
Give the user a **clear, concise, and direct answer** to their
question — like a helpful expert explaining findings in plain English.

STYLE:
- Conversational but professional — imagine a senior researcher
  briefing a colleague over coffee.
- Short paragraphs (2-3 sentences each).  No walls of text.
- Use natural citations: "According to Zhang et al. (2022), ..." or
  "A 2021 survey found that ..."  — NOT full paper titles inline.
- Lead with the key takeaway, then supporting details.
- If the evidence has conflicts, say so plainly:
  "Interestingly, the evidence is mixed — ..."
- End with ONE sentence on confidence:
  "Overall, the evidence is [strong/moderate/limited]."
- Total length: **100-200 words**.  Brevity is king.
- Do NOT use bullet points, numbered lists, or headers.
- Do NOT mention pipeline internals (chunks, similarity scores, etc.).
- Do NOT invent facts beyond what the evidence shows.

─── PIPELINE OUTPUT ───

{pipeline_output}

─── END OF PIPELINE OUTPUT ───

Now give the user a brief, expert answer:
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
