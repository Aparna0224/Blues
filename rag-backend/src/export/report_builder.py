"""Report builder for downloadable comprehensive guides (Markdown + PDF)."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List


class ReportBuilder:
    """Build report artifacts from structured analysis data."""

    def __init__(self, system_name: str = "Blues") -> None:
        self.system_name = system_name

    def build_markdown(self, analysis: Dict[str, Any]) -> str:
        query = analysis.get("query", "")
        generated_at = analysis.get("generated_at") or datetime.utcnow().isoformat()
        references = analysis.get("references", [])
        sub_sections = analysis.get("sub_questions", [])
        summary = analysis.get("final_summary", "")

        lines: List[str] = []
        lines.append(f"# {self.system_name} — Comprehensive Research Guide")
        lines.append("")
        lines.append("## Title Page")
        lines.append(f"- **Query:** {query}")
        lines.append(f"- **Generated at:** {generated_at}")
        lines.append(f"- **Total papers used:** {len(references)}")
        lines.append(f"- **System:** {self.system_name}")
        lines.append("")

        for i, sub in enumerate(sub_sections, 1):
            lines.append(f"## {i}. Sub-question: {sub.get('question', '')}")
            lines.append("")

            papers = sub.get("papers", [])
            if not papers:
                lines.append("_No evidence available for this sub-question._")
                lines.append("")
            for p in papers:
                title = p.get("paper_title", "Unknown")
                year = p.get("paper_year", "N/A")
                doi = p.get("doi") or ""
                link = p.get("link") or ""
                lines.append(f"### 📄 {title} ({year})")
                if doi:
                    lines.append(f"- DOI: {doi}")
                if link:
                    lines.append(f"- Link: {link}")
                lines.append("")

                for u in p.get("evidence_units", []):
                    lines.append(f"- **Chunk ID:** `{u.get('chunk_id', '')}`")
                    lines.append(f"  - Section: {u.get('section', 'unknown')}")
                    lines.append(
                        f"  - Location: sentences {u.get('location_start', '?')}–{u.get('location_end', '?')}"
                    )
                    lines.append(
                        f"  - Relevance: {float(u.get('relevance', 0.0)):.2f} | Confidence: {float(u.get('confidence', 0.0)):.2f} ({u.get('confidence_band', 'N/A')})"
                    )
                    lines.append(f"  - Evidence: {u.get('text', '').strip()}")
                    lines.append("")

            lines.append("### ⚠ Cross-Paper Conflict Analysis")
            conflicts = sub.get("conflicts", [])
            if conflicts:
                for c in conflicts[:3]:
                    lines.append(f"- Claim A: \"{c.get('claim_a', '')}\"")
                    lines.append(f"- Claim B: \"{c.get('claim_b', '')}\"")
                    lines.append(f"- Type: {c.get('type', 'N/A')} | Strength: {float(c.get('strength', 0.0)):.2f}")
                    lines.append(f"- Explanation: {c.get('explanation', '')}")
                    lines.append("")
            else:
                lines.append("No significant conflicts detected because cross-paper claims are aligned or not contradictory on overlapping topics.")
                lines.append("")

            lines.append("### 📊 Comparison Summary")
            lines.append(sub.get("comparison_text", "No comparison summary available."))
            lines.append("")
            lines.append("### 🧠 Sub-question Mini-summary")
            lines.append(sub.get("mini_summary", "No mini-summary available."))
            lines.append("")

        lines.append("## 🧠 Final AI Summary")
        lines.append(summary or "No final summary available.")
        lines.append("")

        lines.append("## References")
        if not references:
            lines.append("No references available.")
        for r in references:
            title = r.get("title", "Unknown")
            year = r.get("year", "N/A")
            doi = r.get("doi") or ""
            link = r.get("link") or ""
            lines.append(f"- {title} ({year})")
            lines.append(f"  - DOI: {doi if doi else 'N/A'}")
            lines.append(f"  - Link: {link if link else 'N/A'}")

        lines.append("")
        return "\n".join(lines)

    def build_pdf(self, analysis: Dict[str, Any]) -> bytes:
        """Build a simple readable PDF report.

        Uses reportlab if available; otherwise returns UTF-8 markdown bytes as fallback.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        except Exception:
            # Fallback keeps endpoint functional in environments without reportlab.
            return self.build_markdown(analysis).encode("utf-8")

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        story = []

        md = self.build_markdown(analysis)
        for line in md.split("\n"):
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 6))
                continue
            if stripped.startswith("# "):
                story.append(Paragraph(f"<b>{stripped[2:]}</b>", styles["Title"]))
            elif stripped.startswith("## "):
                story.append(Paragraph(f"<b>{stripped[3:]}</b>", styles["Heading2"]))
            elif stripped.startswith("### "):
                story.append(Paragraph(f"<b>{stripped[4:]}</b>", styles["Heading3"]))
            else:
                safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, styles["BodyText"]))

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()
        return pdf_bytes
