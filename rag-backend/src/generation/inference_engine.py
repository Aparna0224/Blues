"""
Enhanced Inference Engine for Elaborate Data Analysis.

Extracts and synthesizes insights from:
- Methodology sections (approach, techniques, assumptions)
- Results sections (findings, metrics, outcomes)
- Related work (context, positioning, gaps)
- Discussion (implications, limitations, future work)

Produces structured inferences with evidence chains.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
from dataclasses import dataclass, field


@dataclass
class InferenceChain:
    """Represents a chain of inference with evidence trail."""
    
    claim: str                          # Main claim being made
    confidence: float                   # 0.0-1.0 confidence level
    evidence_sources: List[str] = field(default_factory=list)
    inference_path: List[str] = field(default_factory=list)  # logical steps
    methodology_support: Optional[str] = None
    experimental_support: Optional[str] = None
    limitation: Optional[str] = None
    implication: Optional[str] = None


@dataclass
class MethodologyInsight:
    """Insight extracted from methodology section."""
    
    technique: str
    assumptions: List[str]
    constraints: List[str]
    scope: str
    validation_method: Optional[str] = None


@dataclass
class ExperimentalFinding:
    """Finding extracted from experiments/results."""
    
    finding: str
    metrics: Dict[str, float]  # e.g., {"accuracy": 0.95, "f1": 0.92}
    conditions: List[str]  # under what conditions
    generalizability: str  # "high", "medium", "low", "unknown"
    exceptions: Optional[str] = None


class InferenceEngine:
    """Extract elaborate inferences from research papers."""
    
    # Section detection patterns
    SECTION_PATTERNS = {
        "methodology": r"(methodology|method|approach|algorithm|technique).*?(?=\n(?:results|findings|discussion|conclusion|experiment)|\Z)",
        "results": r"(results?|findings?|experiment|evaluation).*?(?=\n(?:discussion|conclusion|related|limitation)|\Z)",
        "discussion": r"(discussion|implication|limitation|future).*?(?=\n(?:conclusion|references)|\Z)",
        "abstract": r"(abstract).*?(?=\n(?:introduction|methodology)|\Z)",
    }
    
    # Inference patterns
    INFERENCE_PATTERNS = {
        "claim_evidence": r"(shows|demonstrates|indicates|suggests|reveals|finds|proves)\s+(.+?)(?:\.|;|,)",
        "methodology_assumption": r"(assumes?|assumes?|presumes?|requires?)\s+(.+?)(?:\.|;|,)",
        "limitation": r"(limitation|limitation|caveat|constraint|not\s+.+?for)\s+(.+?)(?:\.|;|,)",
        "implication": r"(imply|implication|implies?|suggests?|indicates?)\s+(.+?)(?:\.|;|,)",
        "metric": r"(accuracy|precision|recall|f1|auc|rmse|mae|mape|r\^2|r-squared|score|success|rate|percentage)\s*(?:of|:|is|=)\s*(\d+\.?\d*|\d+%)",
    }
    
    def __init__(self):
        """Initialize inference engine."""
        self.section_patterns = {k: re.compile(v, re.IGNORECASE | re.DOTALL) 
                               for k, v in self.SECTION_PATTERNS.items()}
        self.inference_patterns = {k: re.compile(v, re.IGNORECASE) 
                                  for k, v in self.INFERENCE_PATTERNS.items()}
    
    # ────────────────────────────────────────────────────────────────────────────
    # High-level API
    # ────────────────────────────────────────────────────────────────────────────
    
    def infer_from_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract comprehensive inferences from retrieved chunks.
        
        Args:
            chunks: List of retrieved chunks with full text
            
        Returns:
            Dictionary with:
            - methodology_insights: List[MethodologyInsight]
            - experimental_findings: List[ExperimentalFinding]
            - inference_chains: List[InferenceChain]
            - synthesis: str (synthesized narrative)
            - confidence: float (overall confidence)
        """
        result = {
            "methodology_insights": [],
            "experimental_findings": [],
            "inference_chains": [],
            "synthesis": "",
            "confidence": 0.0
        }
        
        if not chunks:
            return result
        
        # Extract section-specific text
        full_text = " ".join([c.get("text", "") for c in chunks])
        
        # Extract methodology insights
        methodology_text = self._extract_section(full_text, "methodology")
        if methodology_text:
            result["methodology_insights"] = self._parse_methodology(methodology_text)
        
        # Extract experimental findings
        results_text = self._extract_section(full_text, "results")
        if results_text:
            result["experimental_findings"] = self._parse_experimental_findings(results_text)
        
        # Build inference chains
        result["inference_chains"] = self._build_inference_chains(
            methodology_text or "",
            results_text or "",
            chunks
        )
        
        # Calculate overall confidence
        result["confidence"] = self._calculate_confidence(result)
        
        # Synthesize into narrative
        result["synthesis"] = self._synthesize_narrative(result)
        
        return result
    
    # ────────────────────────────────────────────────────────────────────────────
    # Section Extraction
    # ────────────────────────────────────────────────────────────────────────────
    
    def _extract_section(self, text: str, section: str) -> Optional[str]:
        """Extract a specific section from text."""
        if section not in self.section_patterns:
            return None
        
        match = self.section_patterns[section].search(text)
        return match.group(0) if match else None
    
    # ────────────────────────────────────────────────────────────────────────────
    # Methodology Parsing
    # ────────────────────────────────────────────────────────────────────────────
    
    def _parse_methodology(self, methodology_text: str) -> List[MethodologyInsight]:
        """Extract methodology insights from methodology section."""
        insights = []
        
        # Extract technique mentions
        technique_pattern = re.compile(r"(?:use|employ|apply|utilize|adopt)\s+(?:the\s+)?([^.;]+?)(?:\s+(?:to|for|in)\s|\.)", re.IGNORECASE)
        for match in technique_pattern.finditer(methodology_text):
            technique = match.group(1).strip()
            
            # Extract assumptions
            assumptions = self._extract_assumptions(methodology_text, technique)
            
            # Extract constraints
            constraints = self._extract_constraints(methodology_text, technique)
            
            # Extract scope
            scope = self._extract_scope(methodology_text)
            
            # Extract validation method
            validation = self._extract_validation(methodology_text)
            
            insights.append(MethodologyInsight(
                technique=technique,
                assumptions=assumptions,
                constraints=constraints,
                scope=scope,
                validation_method=validation
            ))
        
        return insights
    
    def _extract_assumptions(self, text: str, context: str) -> List[str]:
        """Extract assumptions from text."""
        assumptions = []
        
        patterns = [
            r"assume[sd]?\s+(?:that\s+)?([^.;]+)",
            r"presume[sd]?\s+(?:that\s+)?([^.;]+)",
            r"require[sd]?\s+(?:that\s+)?([^.;]+)",
            r"following\s+(?:the\s+)?assumption[s]?\s+(?:that\s+)?([^.;]+)",
        ]
        
        for pattern in patterns:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            for match in compiled_pattern.finditer(text):
                assumptions.append(match.group(1).strip())
        
        return assumptions[:3]  # Top 3
    
    def _extract_constraints(self, text: str, context: str) -> List[str]:
        """Extract constraints/limitations."""
        constraints = []
        
        patterns = [
            r"(?:limited|constrained)\s+(?:to|by)\s+([^.;]+)",
            r"constraint[s]?\s+(?:of|on)\s+([^.;]+)",
            r"restricted\s+(?:to|by)\s+([^.;]+)",
        ]
        
        for pattern in patterns:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            for match in compiled_pattern.finditer(text):
                constraints.append(match.group(1).strip())
        
        return constraints[:3]
    
    def _extract_scope(self, text: str) -> str:
        """Extract the scope/context of the study."""
        # Look for dataset size, population, domain mentions
        patterns = [
            r"(?:dataset|corpus|data).*?(?:of|containing|with)\s+([^.;]+?)(?:\s+(?:papers|documents|samples|participants|subjects))",
            r"(?:studied|examined|analyzed)\s+([^.;]+?)(?:\s+(?:papers|documents|articles|datasets))",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "Not specified"
    
    def _extract_validation(self, text: str) -> Optional[str]:
        """Extract validation/evaluation method."""
        patterns = [
            r"(?:validated|evaluated|tested)\s+(?:using|with|through)\s+([^.;]+)",
            r"(?:validation|evaluation)\s+(?:method|approach).*?:\s*([^.;]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    # ────────────────────────────────────────────────────────────────────────────
    # Experimental Findings Parsing
    # ────────────────────────────────────────────────────────────────────────────
    
    def _parse_experimental_findings(self, results_text: str) -> List[ExperimentalFinding]:
        """Extract experimental findings from results section."""
        findings = []
        
        # Extract main claims/findings
        claim_pattern = re.compile(r"(?:show|demonstrate|indicate|find|reveal|achieve)\s+(?:that\s+)?([^.;]+?)(?:\.(?:\s|$))", re.IGNORECASE)
        
        for match in claim_pattern.finditer(results_text):
            finding_text = match.group(1).strip()
            
            # Extract metrics
            metrics = self._extract_metrics(results_text, finding_text)
            
            # Extract conditions
            conditions = self._extract_conditions(results_text)
            
            # Determine generalizability
            generalizability = self._assess_generalizability(results_text)
            
            # Extract exceptions
            exceptions = self._extract_exceptions(results_text)
            
            findings.append(ExperimentalFinding(
                finding=finding_text,
                metrics=metrics,
                conditions=conditions,
                generalizability=generalizability,
                exceptions=exceptions
            ))
        
        return findings
    
    def _extract_metrics(self, text: str, context: str) -> Dict[str, float]:
        """Extract quantitative metrics."""
        metrics = {}
        
        for match in self.inference_patterns["metric"].finditer(text):
            metric_name = match.group(1).lower()
            metric_value = match.group(2).rstrip('%')
            
            try:
                value = float(metric_value)
                if "%" in match.group(0):
                    value = value / 100  # Convert to decimal
                metrics[metric_name] = value
            except ValueError:
                pass
        
        return metrics
    
    def _extract_conditions(self, text: str) -> List[str]:
        """Extract experimental conditions."""
        conditions = []
        
        patterns = [
            r"(?:under|with|in)\s+(?:the\s+)?([^.;]+?)(?:\s+condition)",
            r"(?:when|where)\s+([^.;]+?)(?:\.|\s+(?:and|or))",
        ]
        
        for pattern in patterns:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            for match in compiled_pattern.finditer(text):
                conditions.append(match.group(1).strip())
        
        return conditions[:3]
    
    def _assess_generalizability(self, text: str) -> str:
        """Assess how generalizable the findings are."""
        if re.search(r"(generaliz|universal|broadly|across\s+(?:all|different))", text, re.IGNORECASE):
            return "high"
        elif re.search(r"(specific|particular|limited|certain)", text, re.IGNORECASE):
            return "low"
        elif re.search(r"(some|moderate|certain\s+condition)", text, re.IGNORECASE):
            return "medium"
        return "unknown"
    
    def _extract_exceptions(self, text: str) -> Optional[str]:
        """Extract exceptions or edge cases."""
        patterns = [
            r"(?:except|exception|however|but|although)\s+([^.;]+?)(?:\.|\s+(?:and|or))",
            r"(?:not\s+)?(?:apply|hold)\s+(?:when|where|for)\s+([^.;]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    # ────────────────────────────────────────────────────────────────────────────
    # Inference Chain Building
    # ────────────────────────────────────────────────────────────────────────────
    
    def _build_inference_chains(
        self,
        methodology_text: str,
        results_text: str,
        chunks: List[Dict[str, Any]]
    ) -> List[InferenceChain]:
        """Build inference chains connecting methodology to findings."""
        chains = []
        
        # Extract claims from results
        result_claims = self._extract_claims(results_text)
        
        # For each claim, build inference chain
        for claim in result_claims:
            chain = InferenceChain(
                claim=claim,
                confidence=self._estimate_confidence(claim, results_text),
                evidence_sources=[c.get("paper_title", "Unknown") for c in chunks[:3]],
            )
            
            # Add methodology support
            if methodology_text:
                chain.methodology_support = self._find_methodology_support(claim, methodology_text)
            
            # Add experimental support
            chain.experimental_support = self._find_experimental_support(claim, results_text)
            
            # Add limitations
            chain.limitation = self._find_limitations(claim, results_text)
            
            # Add implications
            chain.implication = self._find_implications(claim, results_text)
            
            # Build inference path
            chain.inference_path = self._build_inference_path(claim, methodology_text, results_text)
            
            chains.append(chain)
        
        return chains
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract main claims from text."""
        claims = []
        
        for match in self.inference_patterns["claim_evidence"].finditer(text):
            claim = match.group(2).strip()
            if len(claim) > 10:  # Filter out very short claims
                claims.append(claim)
        
        return claims[:5]  # Top 5 claims
    
    def _estimate_confidence(self, claim: str, text: str) -> float:
        """Estimate confidence in a claim."""
        confidence = 0.5  # Baseline
        
        # Boost if mentioned multiple times
        mention_count = len(re.findall(re.escape(claim[:30]), text, re.IGNORECASE))
        confidence += min(0.3, mention_count * 0.1)
        
        # Boost if strong language
        strong_verbs = r"(definitively|clearly|strongly|significantly|conclusively)"
        if re.search(strong_verbs, text, re.IGNORECASE):
            confidence += 0.15
        
        # Reduce if qualified
        qualifiers = r"(may|might|suggest|appear|seem|possibly|arguably)"
        if re.search(qualifiers, text, re.IGNORECASE):
            confidence -= 0.15
        
        return max(0.0, min(1.0, confidence))
    
    def _find_methodology_support(self, claim: str, methodology_text: str) -> Optional[str]:
        """Find methodology support for claim."""
        # Look for technique/approach mentioned in both
        techniques = re.findall(r"(?:use|employ|apply)\s+([^.;]+?)(?:\s+to|\.)", methodology_text, re.IGNORECASE)
        for technique in techniques[:1]:
            if any(word in claim.lower() for word in technique.lower().split()):
                return f"Supported by {technique.strip()}"
        return None
    
    def _find_experimental_support(self, claim: str, results_text: str) -> Optional[str]:
        """Find experimental evidence supporting claim."""
        # Look for metrics or measurements
        metrics = self._extract_metrics(results_text, claim)
        if metrics:
            metric_str = ", ".join([f"{k}={v:.3f}" for k, v in list(metrics.items())[:2]])
            return f"Metrics: {metric_str}"
        return None
    
    def _find_limitations(self, claim: str, text: str) -> Optional[str]:
        """Find limitations or caveats."""
        for match in self.inference_patterns["limitation"].finditer(text):
            limitation = match.group(2).strip()
            if len(limitation) > 5:
                return limitation
        return None
    
    def _find_implications(self, claim: str, text: str) -> Optional[str]:
        """Find implications or future directions."""
        for match in self.inference_patterns["implication"].finditer(text):
            implication = match.group(2).strip()
            if len(implication) > 5:
                return implication
        return None
    
    def _build_inference_path(self, claim: str, methodology_text: str, results_text: str) -> List[str]:
        """Build logical inference path: Methodology → Experiment → Finding."""
        path = []
        
        # Step 1: Methodology
        if methodology_text and any(word in methodology_text.lower() for word in claim.lower().split()):
            path.append("Methodology: Technique/approach defined")
        
        # Step 2: Experiment setup
        if results_text:
            path.append("Experiment: Study conducted with defined methodology")
        
        # Step 3: Finding
        path.append(f"Finding: {claim[:80]}...")
        
        return path
    
    # ────────────────────────────────────────────────────────────────────────────
    # Synthesis & Confidence Calculation
    # ────────────────────────────────────────────────────────────────────────────
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate overall confidence score."""
        components = []
        
        # Methodology completeness
        methodology_count = len(result.get("methodology_insights", []))
        components.append(min(1.0, methodology_count / 3))
        
        # Findings count
        findings_count = len(result.get("experimental_findings", []))
        components.append(min(1.0, findings_count / 3))
        
        # Inference chains
        chains = result.get("inference_chains", [])
        if chains:
            avg_chain_confidence = sum(c.confidence for c in chains) / len(chains)
            components.append(avg_chain_confidence)
        else:
            components.append(0.0)
        
        return sum(components) / len(components) if components else 0.0
    
    def _synthesize_narrative(self, result: Dict[str, Any]) -> str:
        """Synthesize findings into coherent narrative."""
        narrative = []
        
        # Opening: Methodology summary
        insights = result.get("methodology_insights", [])
        if insights:
            insight = insights[0]
            narrative.append(f"The study employs {insight.technique} under {insight.scope}.")
        
        # Main findings
        chains = result.get("inference_chains", [])
        if chains:
            main_chain = chains[0]
            narrative.append(f"\nKey Finding: {main_chain.claim}")
            
            if main_chain.methodology_support:
                narrative.append(f"({main_chain.methodology_support})")
            
            if main_chain.experimental_support:
                narrative.append(f"\n{main_chain.experimental_support}")
        
        # Implications
        if chains and chains[0].implication:
            narrative.append(f"\nImplication: {chains[0].implication}")
        
        # Limitations
        if chains and chains[0].limitation:
            narrative.append(f"\nLimitation: {chains[0].limitation}")
        
        return " ".join(narrative)
