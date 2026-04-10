"""Verification Agent for Deterministic Confidence Scoring."""
from typing import Dict, Any, List

class VerifierAgent:
    """Calculates deterministic confidence of the retrieval/generation."""
    
    def verify(self, reranked_chunks: List[Dict[str, Any]], answer_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes strict heuristics to compute: C = 0.5*S + 0.3*D + 0.2*E.
        """
        if not reranked_chunks:
            return {"confidence": 0.0, "needs_expansion": True, "reason": "No chunks provided"}
            
        # S: Similarity Average (Extract best scores)
        sims = [float(c.get("similarity_score", c.get("rrf_score", 0.0))) for c in reranked_chunks]
        S = sum(sims) / len(sims) if sims else 0.0
        
        # D: Source Diversity
        sources = {c.get("paper_id", c.get("url", str(i))) for i, c in enumerate(reranked_chunks)}
        D = min(len(sources) / 3.0, 1.0) # Assume 3 unique papers is ideal (100%)
        
        # E: Evidence Density
        ev_count = sum(1 for c in reranked_chunks if c.get("evidence_sentence"))
        E = min(ev_count / max(len(reranked_chunks), 1), 1.0)
        
        # Base C = 0.5S + 0.3D + 0.2E
        C = (0.5 * S) + (0.3 * D) + (0.2 * E)
        
        penalties = []
        if len(sources) == 1:
            C *= 0.8
            penalties.append("Single Source Penalty")
            
        if S < 0.3:
            C *= 0.7
            penalties.append("Low Similarity Penalty")
            
        # "Conflicts" requires cross-claim verification, which can be expensive. 
        # For determinism, we proxy it via low D or manual text heuristic:
        answer_text = str(answer_obj.get("answer", "")).lower()
        if "conflict" in answer_text or "disagree" in answer_text:
            C *= 0.9
            penalties.append("Explicit Conflict Penalty")
            
        needs_expansion = bool(C < 0.45 or len(reranked_chunks) == 0)
        
        print(f"✅ [VerifierNode] Scored C={C:.2f} (S={S:.2f}, D={D:.2f}, E={E:.2f}). Needs expand? {needs_expansion}")
        
        return {
            "confidence": round(C, 2),
            "similarity_avg": round(S, 2),
            "diversity_score": round(D, 2),
            "evidence_density": round(E, 2),
            "penalties": penalties,
            "needs_expansion": needs_expansion
        }
