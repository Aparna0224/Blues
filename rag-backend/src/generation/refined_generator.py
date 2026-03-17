"""
Refined Answer Generator with Professional Formatting.

Generates publication-quality, well-structured answers with:
- Elaborate inference chains
- Structured methodology → findings → implications
- Professional presentation with proper citations
- Nuanced confidence levels and limitations
"""

from typing import List, Dict, Any, Optional
import json
from dataclasses import asdict

from src.llm.base import BaseLLM
from src.generation.inference_engine import InferenceEngine, InferenceChain


class RefinedAnswerGenerator:
    """Generate refined, professional, well-structured answers."""
    
    # ────────────────────────────────────────────────────────────────────────────
    # Refined Prompts (Stage 3 - Enhanced Answer Generation)
    # ────────────────────────────────────────────────────────────────────────────
    
    REFINED_ANSWER_PROMPT = """\
You are a senior research analyst preparing a comprehensive, well-structured 
research brief. Your task is to synthesize evidence from multiple academic papers 
into a clear, professional answer to a research question.

───── RESEARCH CONTEXT ─────
Main Question: {main_question}

Sub-Questions (conceptual breakdown):
{sub_questions_formatted}

───── METHODOLOGY SUMMARY ─────
The retrieved papers employ these approaches:
{methodology_summary}

Scope: {scope}
Key Techniques: {techniques}

───── KEY FINDINGS ─────
Evidence-backed findings:
{findings_formatted}

Quantitative Support:
{metrics_formatted}

───── YOUR TASK ─────

Structure your answer as follows:

1. **EXECUTIVE SUMMARY** (2-3 sentences)
   - Direct answer to the main question
   - Primary evidence strength (high/moderate/limited)

2. **DETAILED ANALYSIS** (3-4 paragraphs)
   For each sub-question:
   - Findings organized by topic
   - Supporting evidence with metrics
   - Caveats and conditions
   - Natural citations: "According to [Author] (Year)..." or "A [Year] study found..."

3. **METHODOLOGICAL FOUNDATION**
   - Brief explanation of techniques used
   - Study scope and limitations
   - How findings were validated

4. **PRACTICAL IMPLICATIONS**
   - Real-world applications
   - When findings apply (and when they don't)
   - Confidence level and reasoning

5. **GAPS & FUTURE DIRECTIONS**
   - Unresolved questions
   - Limitations acknowledged
   - Recommended next steps

───── WRITING GUIDELINES ─────
✓ Use clear, professional language (suitable for researcher audience)
✓ Prioritize accuracy over eloquence
✓ Include confidence indicators: "strongly supported", "suggests", "indicates"
✓ Connect methodology to findings explicitly
✓ Acknowledge limitations and exceptions
✓ Use natural citations, not internal score references
✓ Format with headers and logical flow
✗ Do NOT use bullet points for main content (use paragraphs)
✗ Do NOT mention "chunks", "retrieval", or pipeline internals
✗ Do NOT invent facts beyond evidence
✗ Do NOT use overly academic jargon

───── SYNTHESIS INPUT ─────

{inference_summary}

───── END INPUT ─────

Now provide a comprehensive, well-structured research answer following the 
5-section structure above. Focus on clarity, accuracy, and professional presentation.
"""
    
    # ────────────────────────────────────────────────────────────────────────────
    # Evidence-Based Verification Prompt
    # ────────────────────────────────────────────────────────────────────────────
    
    EVIDENCE_VERIFICATION_PROMPT = """\
You are a research quality auditor. Review the following answer against the 
provided evidence to verify accuracy and identify gaps.

ORIGINAL QUESTION:
{main_question}

GENERATED ANSWER:
{answer}

AVAILABLE EVIDENCE:
{evidence_dump}

YOUR VERIFICATION TASK:

1. Check each major claim in the answer
2. Verify it has supporting evidence
3. Identify unsupported statements (if any)
4. Suggest improvements for clarity or completeness
5. Flag any overstated or unsupported conclusions

Format your review as:

✓ VERIFIED CLAIMS:
- [Claim] → [Evidence source and strength]

⚠ PARTIAL CLAIMS (need nuance):
- [Claim] → [What's missing or needs qualification]

✗ UNSUPPORTED CLAIMS (must revise):
- [Claim] → [Why it's not supported]

📌 IMPROVEMENT SUGGESTIONS:
1. [Suggestion with specific line/section]
2. ...

CONFIDENCE ASSESSMENT:
- Overall accuracy: [HIGH/MODERATE/LOW]
- Missing coverage: [What's not discussed]
- Recommended revisions: [Key changes]

After review, provide a revised version that:
- Removes unsupported claims
- Adds necessary qualifications
- Maintains professional tone
- Prioritizes evidence-backed assertions
"""
    
    # ────────────────────────────────────────────────────────────────────────────
    # Structured Refinement Prompt
    # ────────────────────────────────────────────────────────────────────────────
    
    STRUCTURED_REFINEMENT_PROMPT = """\
You are an expert science writer specializing in clear, structured communication 
of research findings. Your task is to refine an existing answer to make it more 
professional, well-structured, and impactful.

CURRENT ANSWER:
{current_answer}

METADATA:
- Main Question: {main_question}
- Evidence Quality: {evidence_quality}
- Number of Sources: {num_sources}
- Confidence Level: {confidence_level}

REFINEMENT PRIORITIES:

1. **Structural Improvement**
   - Ensure 5-section format (Executive Summary → Analysis → Methodology → Implications → Gaps)
   - Add clear section headers
   - Use smooth transitions between paragraphs
   - Maintain logical flow

2. **Evidence Enhancement**
   - Make citations more natural: "According to [Author] (Year)..." not "[ref #]"
   - Integrate metrics naturally: "achieved 95% accuracy" not "metric: accuracy=0.95"
   - Connect methodology to findings explicitly
   - Show chain of reasoning

3. **Clarity & Professionalism**
   - Replace jargon with explanations
   - Use active voice where possible
   - Vary sentence length for readability
   - Maintain objective, authoritative tone

4. **Completeness**
   - Address all sub-questions
   - Include practical implications
   - Acknowledge limitations explicitly
   - Suggest future research directions

5. **Precision**
   - Remove hedging where evidence is strong
   - Add qualifiers where evidence is weak
   - Distinguish between findings and speculation
   - Specify scope and conditions

OUTPUT FORMAT:

**STRUCTURAL ANALYSIS:**
- Current structure: [describe]
- Improvements needed: [list]

**REFINED ANSWER:**
[Full refined answer following 5-section structure]

**QUALITY NOTES:**
- Evidence coverage: [assess]
- Confidence reflected: [assess]
- Professional presentation: [assess]
- Remaining gaps: [list if any]

Produce the refined answer immediately after the analysis section, ready to 
present to a research audience.
"""
    
    def __init__(self, llm: BaseLLM):
        """
        Initialize refined answer generator.
        
        Args:
            llm: BaseLLM instance (Gemini, Groq, or local Ollama)
        """
        self.llm = llm
        self.inference_engine = InferenceEngine()
    
    # ────────────────────────────────────────────────────────────────────────────
    # Main Generation Pipeline
    # ────────────────────────────────────────────────────────────────────────────
    
    def generate_refined_answer(
        self,
        question: str,
        sub_questions: List[str],
        chunks: List[Dict[str, Any]],
        verification_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generate a refined, professional answer with all enhancements.
        
        Args:
            question: Main research question
            sub_questions: Decomposed sub-questions
            chunks: Retrieved evidence chunks
            verification_result: Optional verification metrics
            
        Returns:
            Dictionary with:
            - answer: The refined answer
            - evidence_summary: Summary of evidence used
            - confidence: Overall confidence score
            - structure_notes: Notes on answer structure
        """
        
        print(f"🔄 Extracting inferences from {len(chunks)} chunks...")
        
        # Step 1: Extract elaborate inferences
        inference_result = self.inference_engine.infer_from_chunks(chunks)
        
        # Step 2: Format context for prompt
        methodology_summary = self._format_methodology_summary(
            inference_result.get("methodology_insights", [])
        )
        
        findings_summary = self._format_findings_summary(
            inference_result.get("experimental_findings", [])
        )
        
        inference_summary = self._format_inference_summary(
            inference_result.get("inference_chains", [])
        )
        
        metrics_summary = self._format_metrics_summary(chunks)
        
        # Step 3: Build refined prompt
        prompt = self.REFINED_ANSWER_PROMPT.format(
            main_question=question,
            sub_questions_formatted=self._format_sub_questions(sub_questions),
            methodology_summary=methodology_summary,
            scope=self._extract_scope(chunks),
            techniques=self._extract_techniques(inference_result),
            findings_formatted=findings_summary,
            metrics_formatted=metrics_summary,
            inference_summary=inference_summary
        )
        
        # Step 4: Generate answer with LLM
        print(f"✍️  Generating refined answer from {self.llm}...")
        answer = self.llm.generate(prompt)
        
        # Step 5: Optional verification & refinement
        if verification_result and verification_result.get("confidence_score", 0) < 0.7:
            print(f"🔍 Verifying answer quality (confidence: {verification_result['confidence_score']:.2f})...")
            answer = self._verify_and_refine(
                answer=answer,
                question=question,
                chunks=chunks,
                evidence_quality=self._assess_evidence_quality(chunks)
            )
        
        return {
            "answer": answer,
            "evidence_summary": inference_summary,
            "confidence": inference_result.get("confidence", 0.0),
            "structure_notes": "5-section format: Executive Summary, Detailed Analysis, Methodology, Implications, Gaps",
            "sources_count": len(set(c.get("paper_id") for c in chunks)),
            "chunks_used": len(chunks)
        }
    
    # ────────────────────────────────────────────────────────────────────────────
    # Formatting Helpers
    # ────────────────────────────────────────────────────────────────────────────
    
    def _format_sub_questions(self, sub_questions: List[str]) -> str:
        """Format sub-questions for prompt."""
        if not sub_questions:
            return "Not decomposed"
        
        formatted = []
        for i, sq in enumerate(sub_questions, 1):
            formatted.append(f"  {i}. {sq}")
        return "\n".join(formatted)
    
    def _format_methodology_summary(self, insights: List[Any]) -> str:
        """Format methodology insights for prompt."""
        if not insights:
            return "No specific methodology details extracted."
        
        summary = []
        for insight in insights[:3]:  # Top 3
            if hasattr(insight, 'technique'):
                summary.append(f"- {insight.technique}")
                if hasattr(insight, 'assumptions') and insight.assumptions:
                    summary.append(f"  Assumptions: {', '.join(insight.assumptions[:2])}")
            else:
                summary.append(f"- {insight}")
        
        return "\n".join(summary) if summary else "Standard methodologies employed"
    
    def _format_findings_summary(self, findings: List[Any]) -> str:
        """Format experimental findings for prompt."""
        if not findings:
            return "No specific findings extracted."
        
        summary = []
        for finding in findings[:5]:
            if hasattr(finding, 'finding'):
                summary.append(f"- {finding.finding}")
                if hasattr(finding, 'generalizability'):
                    summary.append(f"  (Generalizability: {finding.generalizability})")
            else:
                summary.append(f"- {finding}")
        
        return "\n".join(summary) if summary else "Findings to be detailed in analysis"
    
    def _format_inference_summary(self, chains: List[InferenceChain]) -> str:
        """Format inference chains for prompt."""
        if not chains:
            return "Evidence chains to be synthesized in analysis."
        
        summary = []
        for chain in chains[:5]:
            summary.append(f"**Claim:** {chain.claim}")
            summary.append(f"**Confidence:** {chain.confidence:.1%}")
            
            if chain.methodology_support:
                summary.append(f"**Methodology Support:** {chain.methodology_support}")
            
            if chain.experimental_support:
                summary.append(f"**Experimental Support:** {chain.experimental_support}")
            
            if chain.limitation:
                summary.append(f"**Limitation:** {chain.limitation}")
            
            summary.append("")
        
        return "\n".join(summary)
    
    def _format_metrics_summary(self, chunks: List[Dict[str, Any]]) -> str:
        """Extract and format key metrics from chunks."""
        metrics = {}
        
        for chunk in chunks:
            text = chunk.get("text", "")
            
            # Simple metric extraction
            import re
            metric_pattern = r"(accuracy|precision|recall|f1|auc|score)\s*(?:of|:)?\s*(\d+\.?\d*)"
            
            for match in re.finditer(metric_pattern, text, re.IGNORECASE):
                metric_name = match.group(1).lower()
                value = float(match.group(2))
                if metric_name not in metrics:
                    metrics[metric_name] = []
                metrics[metric_name].append(value)
        
        if not metrics:
            return "Metrics embedded in detailed findings"
        
        summary = []
        for metric, values in metrics.items():
            avg_value = sum(values) / len(values)
            summary.append(f"- {metric.title()}: {avg_value:.3f} (from {len(values)} studies)")
        
        return "\n".join(summary)
    
    def _extract_scope(self, chunks: List[Dict[str, Any]]) -> str:
        """Extract study scope from chunks."""
        unique_papers = set(c.get("paper_id") for c in chunks)
        return f"Analysis synthesizes {len(unique_papers)} papers with {len(chunks)} evidence chunks"
    
    def _extract_techniques(self, inference_result: Dict[str, Any]) -> str:
        """Extract key techniques from inferences."""
        insights = inference_result.get("methodology_insights", [])
        if not insights:
            return "Multiple research methodologies"
        
        techniques = []
        for insight in insights[:3]:
            if hasattr(insight, 'technique'):
                techniques.append(insight.technique)
        
        return ", ".join(techniques) if techniques else "Various techniques"
    
    # ────────────────────────────────────────────────────────────────────────────
    # Verification & Refinement
    # ────────────────────────────────────────────────────────────────────────────
    
    def _verify_and_refine(
        self,
        answer: str,
        question: str,
        chunks: List[Dict[str, Any]],
        evidence_quality: str
    ) -> str:
        """Verify answer against evidence and refine if needed."""
        
        # Build evidence dump for verification
        evidence_dump = self._build_evidence_dump(chunks)
        
        # Verification prompt
        verification_prompt = self.EVIDENCE_VERIFICATION_PROMPT.format(
            main_question=question,
            answer=answer,
            evidence_dump=evidence_dump
        )
        
        # Get verification from LLM
        verification = self.llm.generate(verification_prompt)
        
        # Extract refined answer if provided
        if "REFINED VERSION" in verification or "revised version" in verification.lower():
            # Try to extract the revised answer
            import re
            revised = re.search(r"(?:REVISED|revised)\s+(?:VERSION|version)?[\s:]*(.+?)(?=\n\n|\Z)", 
                              verification, re.DOTALL)
            if revised:
                return revised.group(1).strip()
        
        return answer  # Return original if verification didn't produce revision
    
    def _build_evidence_dump(self, chunks: List[Dict[str, Any]]) -> str:
        """Build a structured dump of evidence for verification."""
        dump = []
        
        for i, chunk in enumerate(chunks[:10], 1):  # Top 10
            dump.append(f"\nEVIDENCE {i}:")
            dump.append(f"Source: {chunk.get('paper_title', 'Unknown')} ({chunk.get('paper_year', '?')})")
            dump.append(f"Section: {chunk.get('section', 'body')}")
            dump.append(f"Relevance: {chunk.get('similarity_score', 0):.3f}")
            dump.append(f"Text: {chunk.get('text', '')[:300]}...")
        
        return "\n".join(dump)
    
    def _assess_evidence_quality(self, chunks: List[Dict[str, Any]]) -> str:
        """Assess overall quality of evidence."""
        if not chunks:
            return "NO_EVIDENCE"
        
        avg_score = sum(c.get("similarity_score", 0) for c in chunks) / len(chunks)
        
        if avg_score > 0.7:
            return "HIGH"
        elif avg_score > 0.5:
            return "MODERATE"
        else:
            return "LOW"


# ────────────────────────────────────────────────────────────────────────────
# Export for use in main pipeline
# ────────────────────────────────────────────────────────────────────────────

def generate_professional_answer(
    llm: BaseLLM,
    question: str,
    sub_questions: List[str],
    chunks: List[Dict[str, Any]],
    verification_result: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to generate professional answer.
    
    Usage::
        
        from src.llm.factory import get_llm
        from src.generation.refined_generator import generate_professional_answer
        
        llm = get_llm()
        answer_dict = generate_professional_answer(
            llm=llm,
            question="What is explainable AI?",
            sub_questions=["What are XAI techniques?", "Why is it important?"],
            chunks=retrieved_chunks,
            verification_result=verification_result
        )
        print(answer_dict["answer"])
    """
    generator = RefinedAnswerGenerator(llm)
    return generator.generate_refined_answer(
        question=question,
        sub_questions=sub_questions,
        chunks=chunks,
        verification_result=verification_result
    )
