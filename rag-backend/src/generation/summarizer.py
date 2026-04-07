"""Pipeline Summarizer — evidence-grounded literature-review synthesis (Stage 5).

Takes the full Stage 4 output (grouped answer with claims, evidence,
verification metrics) and sends it to the configured LLM to produce
a professional, clear, publication-grade narrative summary.

The summary is appended to the existing output — it does NOT replace
or modify any Stage 4 content.
"""

import re
from collections import Counter
from typing import Dict, Any, Optional, List

from src.llm.base import BaseLLM


# ── Prompt template ──────────────────────────────────────────────

_SUMMARY_PROMPT = """\
You are an expert research analyst writing a high-quality literature review synthesis.

Your task is to transform the provided evidence-grounded draft into a clear, insightful, and academically strong summary.

STRICT RULES:
- Use ONLY the provided content — do not introduce external knowledge.
- Do NOT copy sentences directly — synthesize and rephrase.
- Every paragraph must convey a meaningful insight, not just description.
- Ensure all sentences are complete and coherent.

FORBIDDEN PHRASES — never use these:
'computational and analytical methods'
'various approaches'
'trade-offs in interpretability'
'implementation emphasis'
'methodological variation'
'patterns observed'
'mixed approaches'
'no strong trend'
Use specific terms from the evidence draft provided.

═══════════════════════════════
WRITING GOAL
═══════════════════════════════

Produce a structured, publication-quality synthesis that:

1. Clearly explains what the topic is about
2. Identifies the MAIN approaches used across papers
3. Explains how these approaches DIFFER (not just that they exist)
4. Highlights key findings and patterns
5. Identifies any trends
6. Ends with a strong, conclusive insight

═══════════════════════════════
REQUIRED STRUCTURE
═══════════════════════════════

1) Topic Overview  
- Define the problem clearly  
- Mention scope of evidence (sub-questions + papers)

2) Key Approaches  
- Identify dominant methods using the specific terms from the draft  
- Explain their purpose  

3) Agreements and Differences  
- What do papers agree on?  
- Where do they differ (method, outcome, approach)?  
- Be explicit and comparative  

4) Overall Insight / Conclusion  
- What does the literature collectively indicate?  
- Mention any trend or limitation  

═══════════════════════════════
IMPORTANT
═══════════════════════════════

The Comparison Summary section in the pipeline output ALREADY shows which
papers use which methods and what results they report. Your 4 paragraphs
must NOT repeat those paper-level details. Instead, your job is to answer:
Given what these papers collectively show, what should the researcher
understand, believe, or do next? Focus on insight, implication, and
research direction — not description.

The deterministic draft ALREADY contains the key terms and conflict info.
Your job is to SYNTHESIZE and ADD INSIGHT, not describe methods again.

═══════════════════════════════
CONTEXT
═══════════════════════════════

Query:
{query}

Evidence-based synthesis draft:
{deterministic_summary}

═══════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════

- Write in clear academic prose
- Use 4 short paragraphs (one per section)
- Ensure logical flow between sections
- No bullet points
- No placeholders
- No repetition
- Explicitly mention method families, findings, and trend direction when supported.
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
        """Create an evidence-grounded synthesis without relying on LLM inference."""
        if not analysis_data or not analysis_data.get("sub_questions"):
            return (
                f"For the query '{query}', the available evidence indicates "
                "multiple perspectives addressing the same problem from complementary angles.\n\n"
                "The retrieved studies describe approaches that prioritize either "
                "interpretability, automation, or robustness under practical constraints.\n\n"
                "Reported findings are directionally related but not identical, because "
                "papers evaluate different datasets, assumptions, and implementation choices.\n\n"
                "Overall, the literature supports a converging objective while highlighting "
                "trade-offs that should guide method selection in context."
            )

        # Step 1 — Count evidence
        sub_sections = analysis_data.get("sub_questions", [])
        num_subquestions = len(sub_sections)
        num_papers = len(analysis_data.get("references", []))
        all_units: List[Dict[str, Any]] = []

        for sub in sub_sections:
            papers = sub.get("papers", [])
            for p in papers:
                all_units.extend(p.get("evidence_units", []))

        # Step 2 — Extract key terms from evidence text
        key_terms = self._extract_key_terms(all_units)
        terms_str = ", ".join(key_terms[:6]) if key_terms else "the studied topics"

        # Step 3 — Check for conflicts
        try:
            from src.comparison.conflict_detector import ConflictDetector
            conflicts = ConflictDetector.detect_conflicts(all_units)
            has_conflicts = len(conflicts) > 0
        except Exception:
            conflicts = []
            has_conflicts = False

        conflict_text = (
            f"The evidence includes {len(conflicts)} cross-paper conflict(s), "
            "indicating divergent findings on overlapping topics."
            if has_conflicts else
            "Cross-paper claims are directionally aligned on the main topics."
        )

        # Step 4 — Extract section coverage
        sections_seen = set()
        for unit in all_units:
            sections_seen.add(unit.get("section", "unknown"))
        sections_str = ", ".join(sorted(sections_seen)) if sections_seen else "unknown"

        # Step 5 — Build the 4-paragraph deterministic draft
        overview_par = (
            f"This synthesis addresses '{query}' using evidence from "
            f"{num_subquestions} sub-questions and {num_papers} paper(s). "
            f"The key topics in the retrieved evidence include: {terms_str}. "
            f"Evidence spans sections: {sections_str}."
        )
        approaches_par = (
            f"The retrieved papers approach the problem using methods and frameworks "
            f"centered on: {terms_str}. "
            f"These approaches vary in their emphasis on interpretability, automation, "
            f"and generalization across problem settings."
        )
        differences_par = (
            f"The papers agree on the core problem framing but differ in scope "
            f"and methodology. {conflict_text}"
        )
        conclusion_par = (
            f"Overall, the literature provides "
            f"{'conflicting' if has_conflicts else 'convergent'} evidence on {query}. "
            f"The evidence base has {num_papers} paper(s), which is "
            f"{'sufficient for moderate' if num_papers >= 3 else 'limited — treat conclusions as preliminary'} "
            f"confidence in the findings."
        )

        return "\n\n".join([overview_par, approaches_par, differences_par, conclusion_par])

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
