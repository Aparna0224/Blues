"""Pipeline Summarizer — evidence-grounded literature-review synthesis (Stage 5).

Takes the full Stage 4 output (grouped answer with claims, evidence,
verification metrics) and sends it to the configured LLM to produce
a professional, clear, publication-grade narrative summary.

The summary is appended to the existing output — it does NOT replace
or modify any Stage 4 content.
"""

import re
import logging
from collections import Counter
from typing import Dict, Any, Optional, List

from src.llm.base import BaseLLM


# ── Prompt template ──────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are an expert research analyst writing a structured literature review.

Your task: transform the evidence-grounded draft below into a clear,
insightful, comparative summary.  You MUST output EXACTLY four sections,
each separated by the delimiter line: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRICT RULES:
- Use ONLY the provided content — do not introduce external knowledge.
- Do NOT copy sentences directly — synthesize and rephrase.
- NEVER use generic phrases: 'various approaches', 'multiple methods',
  'computational and analytical methods', 'trade-offs in interpretability'.
- ALWAYS name specific papers, datasets, models, and metric values.

═══════════════════════════════
REQUIRED OUTPUT FORMAT
═══════════════════════════════

TOPIC OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2-3 sentences: What is the research question? How many papers and
sub-questions were used? Mention the scope (e.g. "5 papers spanning 2019-2024").

PAPER-BY-PAPER COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For EACH paper in the draft, write one compact paragraph:
• Paper title and year
• Datasets used (name them)
• Core methodology / model architecture (name it)
• Key reported results (include metric values)
• Unique contribution vs other papers

CROSS-PAPER ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1-2 paragraphs comparing across papers:
• Which datasets are shared? Which are unique?
• Where do methods agree? Where do they diverge?
• Do results on shared datasets show consistent or conflicting performance?

SYNTHESIS & RESEARCH DIRECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1 paragraph:
• What does the literature collectively indicate?
• What gaps or limitations remain?
• What should a researcher do next?

═══════════════════════════════
CONTEXT
═══════════════════════════════

Query:
{query}

Evidence-based structured draft:
{deterministic_summary}

═══════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════
- Write in clear academic prose
- 4 sections separated by the delimiter ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Every section MUST include specific paper names and data points
- No bullet points in prose paragraphs
- No placeholders
- No generic filler
"""

# ── Stop words for term extraction ───────────────────────────────

_STOP_WORDS = {
    "what", "how", "why", "when", "where", "which", "is", "are",
    "does", "do", "can", "the", "a", "an", "in", "of", "and",
    "or", "to", "for", "on", "with", "by", "from", "as", "at",
    "about", "into", "be", "this", "that", "it", "its", "their",
    "they", "them", "we", "our", "you", "your", "using", "used",
    "use", "uses", "benefits", "benefit", "been", "being", "was",
    "were", "has", "had", "have", "will", "would", "could", "should",
    "may", "might", "shall", "than", "then", "also", "such", "very",
    "just", "only", "both", "each", "every", "some", "any", "most",
    "more", "other", "over", "under", "through", "between", "during",
    "before", "after", "above", "below", "these", "those", "there",
    "here", "while", "where", "when", "not", "but", "however",
    "although", "because", "since", "paper", "papers", "study",
    "studies", "results", "result", "approach", "method", "based",
    "approach", "proposed", "different", "provides", "show", "shows",
    "shown", "found", "work", "present", "presented", "data",
}

# ── Generic phrases to detect LLM filler ─────────────────────────

_GENERIC_PHRASES = [
    "computational and analytical methods",
    "various approaches",
    "methodological variation",
    "trade-offs in interpretability",
    "implementation emphasis",
    "patterns observed",
    "mixed approaches",
]


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
        # Validate analysis_data schema — log warnings for missing keys
        from src.utils.analysis_schema import validate_analysis_data
        schema_warnings = validate_analysis_data(analysis_data or {})
        if schema_warnings:
            _log = logging.getLogger(__name__)
            _log.warning(
                "analysis_data has %d schema issue(s) — summary quality may be degraded",
                len(schema_warnings),
            )

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
            if summary_text.lower().startswith("error:"):
                summary_text = deterministic_summary
            # Detect too-short output
            elif not summary_text or len(summary_text.split()) < 40:
                summary_text = deterministic_summary
            else:
                # Detect generic filler (the main new check)
                generic_hits = sum(
                    1 for p in _GENERIC_PHRASES if p in summary_text.lower()
                )
                if generic_hits >= 2:
                    # LLM produced generic filler — use deterministic draft instead
                    summary_text = deterministic_summary
        except Exception as e:
            _ = e
            summary_text = deterministic_summary

        return self._format_summary_block(summary_text, verification_result)

    # ─────────────────────────────────────────────────────────────
    # Key term extraction from evidence
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_key_terms(units: List[Dict[str, Any]], top_n: int = 8) -> List[str]:
        """Extract the most frequent non-trivial terms from evidence units.

        Tokenizes claim + text from each evidence unit, removes stop words,
        and returns the top N most frequent meaningful terms.
        """
        if not units:
            return []

        combined_text = " ".join(
            (u.get("claim") or "") + " " + (u.get("text") or "")
            for u in units
        ).lower()

        # Tokenize and clean
        raw_words = re.findall(r'[a-z][a-z\-]+[a-z]', combined_text)
        filtered = [
            w for w in raw_words
            if len(w) > 3 and w not in _STOP_WORDS
        ]

        if not filtered:
            return []

        counts = Counter(filtered)
        return [term for term, _ in counts.most_common(top_n)]

    # ─────────────────────────────────────────────────────────────
    # Deterministic summary builder
    # ─────────────────────────────────────────────────────────────

    def _deterministic_literature_summary(
        self,
        analysis_data: Optional[Dict[str, Any]],
        grouped_answer: str,
        query: str,
    ) -> str:
        """Create a structured comparison draft from the comparison matrix.

        This is deterministic — no LLM call.  It builds 6 labelled sections
        that the LLM prompt can reshape into publication prose.  If the
        comparison matrix is missing, falls back to the old 4-paragraph
        approach.
        """
        if not analysis_data or not analysis_data.get("sub_questions"):
            return (
                f"For the query '{query}', the available evidence indicates "
                "multiple perspectives addressing the same problem from complementary angles.\n\n"
                "Insufficient structured data to generate a comparison table."
            )

        matrix = analysis_data.get("paper_comparison_matrix", [])
        overlap = analysis_data.get("cross_paper_dataset_overlap", {})
        sub_sections = analysis_data.get("sub_questions", [])
        num_subquestions = len(sub_sections)
        num_papers = len(analysis_data.get("references", []))

        # Collect all evidence units for conflict detection
        all_units: List[Dict[str, Any]] = []
        for sub in sub_sections:
            for p in sub.get("papers", []):
                all_units.extend(p.get("evidence_units", []))

        lines: List[str] = []

        # ── SECTION 1: Paper Overview Table ──────────────────────
        lines.append("## SECTION 1: PAPER OVERVIEW TABLE")
        lines.append("")
        lines.append("| Title | Year | Datasets | Method / Model | Key Metrics |")
        lines.append("|-------|------|----------|----------------|-------------|")
        for row in matrix:
            title = (row.get("title") or "Unknown")[:50]
            year = row.get("year", "N/A")
            datasets = ", ".join(row.get("datasets", [])[:3]) or "—"
            models = ", ".join(row.get("model_names", [])[:2]) or "—"
            methods = ", ".join(row.get("method_keywords", [])[:2])
            method_str = f"{models}" + (f" ({methods})" if methods else "")
            metrics = ", ".join(row.get("metrics", [])[:3]) or "—"
            lines.append(f"| {title} | {year} | {datasets} | {method_str} | {metrics} |")
        lines.append("")

        # ── SECTION 2: Methodology Comparison ────────────────────
        lines.append("## SECTION 2: METHODOLOGY COMPARISON")
        lines.append("")
        for row in matrix:
            title = row.get("title", "Unknown")[:50]
            year = row.get("year", "N/A")
            models = ", ".join(row.get("model_names", [])) or "unspecified models"
            methods = ", ".join(row.get("method_keywords", [])) or "general computational pipeline"
            evidence = (row.get("top_evidence") or "")[:150]
            lines.append(
                f"• {title} ({year}): Uses {models} with methodology focused on "
                f"{methods}. Evidence: \"{evidence}...\""
            )
        lines.append("")

        # ── SECTION 3: Dataset Analysis ──────────────────────────
        lines.append("## SECTION 3: DATASET ANALYSIS")
        lines.append("")
        if overlap:
            lines.append("Shared datasets across papers:")
            for ds, papers in overlap.items():
                lines.append(f"  • {ds}: used by {', '.join(papers)}")
        else:
            lines.append("No shared datasets detected across papers.")

        unique_datasets: Dict[str, List[str]] = {}
        for row in matrix:
            for ds in row.get("datasets", []):
                if ds not in overlap:
                    unique_datasets.setdefault(ds, []).append(row.get("title", "Unknown")[:40])
        if unique_datasets:
            lines.append("\nPaper-specific datasets:")
            for ds, papers in list(unique_datasets.items())[:8]:
                lines.append(f"  • {ds}: {', '.join(papers)}")
        lines.append("")

        # ── SECTION 4: Results Comparison ────────────────────────
        lines.append("## SECTION 4: RESULTS COMPARISON")
        lines.append("")
        for row in matrix:
            title = row.get("title", "Unknown")[:50]
            metrics = row.get("metrics", [])
            if metrics:
                lines.append(f"• {title}: {', '.join(metrics[:5])}")
            else:
                lines.append(f"• {title}: No quantitative metrics extracted.")
        lines.append("")

        # ── SECTION 5: Conflicts & Agreements ────────────────────
        lines.append("## SECTION 5: CONFLICTS AND AGREEMENTS")
        lines.append("")
        try:
            from src.comparison.conflict_detector import ConflictDetector
            conflicts = ConflictDetector.detect_conflicts(all_units)
            if conflicts:
                lines.append(f"{len(conflicts)} cross-paper conflict(s) detected:")
                for c in conflicts[:3]:
                    a_title = c.get("a", {}).get("paper_title", "Paper A")[:30]
                    b_title = c.get("b", {}).get("paper_title", "Paper B")[:30]
                    lines.append(
                        f"  • {a_title} vs {b_title}: "
                        f"{c.get('type', 'unknown')} conflict (strength {c.get('strength', 0):.2f})"
                    )
            else:
                lines.append("No cross-paper conflicts detected — claims are directionally aligned.")
        except Exception:
            lines.append("Conflict analysis unavailable.")

        if overlap:
            lines.append(f"\nAgreement: {len(overlap)} dataset(s) shared across papers allow direct comparison.")
        lines.append("")

        # ── SECTION 6: Raw Stats ─────────────────────────────────
        lines.append("## SECTION 6: RAW STATS")
        lines.append("")
        lines.append(f"• Papers analyzed: {num_papers}")
        lines.append(f"• Sub-questions addressed: {num_subquestions}")
        lines.append(f"• Evidence units: {len(all_units)}")
        conf = analysis_data.get("confidence_score")
        if isinstance(conf, (int, float)):
            lines.append(f"• Pipeline confidence: {conf:.2f}")
        lines.append("")

        return "\n".join(lines)

    SECTION_DELIMITER = "━" * 40

    @staticmethod
    def _format_summary_block(
        summary_text: str,
        verification_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Wrap the LLM summary in a presentable output block.

        Uses Unicode ``━`` delimiters between sections.  The frontend
        splits on this pattern to render structured cards.
        """
        lines = [
            "",
            "RESEARCH SUMMARY",
            "",
            summary_text,
            "",
        ]

        # Append confidence footer as a coloured badge
        if verification_result:
            score = verification_result.get("confidence_score", 0)
            if score >= 0.75:
                level = "HIGH"
            elif score >= 0.50:
                level = "MODERATE"
            else:
                level = "LOW"
            lines.append(f"Pipeline Confidence: {score:.2f} ({level})")
            lines.append("")

        return "\n".join(lines)

