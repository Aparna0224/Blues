"""Agentic Generator for Grounded Outputs."""
import json
import re
from typing import Dict, Any, List
from src.llm.base import BaseLLM

class GeneratorAgent:
    """Generates heavily grounded answers based strictly on reranked chunks."""
    
    SYSTEM_PROMPT = """
You are a Grounded Research Synthesis Agent.
Your task is to take a set of retrieved chunks and answering the User Query.

STRICT RULES:
1. ONLY use the provided chunks. DO NOT hallucinate.
2. If the chunks do not contain enough information, state exactly what is missing. Support what you can.
3. You must extract and build a logical summary structured around the Sub-Questions if possible.
4. Output JSON exactly in the requested format.

PROVIDED CONTEXT:
{context}

OUTPUT FORMAT (Valid JSON only):
{
  "answer": "Structured explanation answering the main query based strictly on the text...",
  "claims": [
    "Claim 1...", "Claim 2..."
  ]
}
"""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def generate(self, query: str, sub_queries: List[str], reranked_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates grounded answer from the global reranked chunks."""
        print(f"✍ [GeneratorNode] Structuring grounded answer over {len(reranked_chunks)} chunks...")
        
        # Build strict context payload
        context_blocks = []
        for i, chunk in enumerate(reranked_chunks, 1):
            paper_title = chunk.get("paper_title", "Unknown Paper")
            text = chunk.get("text", "")
            ev_sentence = chunk.get("evidence_sentence", "")
            if ev_sentence:
                context_blocks.append(f"Source [{i} - {paper_title}]\nEvidence Exact: {ev_sentence}\nContext: {text}")
            else:
                context_blocks.append(f"Source [{i} - {paper_title}]\nContext: {text}")
                
        context_str = "\n\n".join(context_blocks)
        
        prompt = self.SYSTEM_PROMPT.replace("{context}", context_str) + f"\n\nUser Query: {query}\nSub-Questions to cover: {sub_queries}\nOutput JSON:"
        
        try:
            raw = self.llm.generate(prompt)
            data = self._parse_json(raw)
            return data
        except Exception as e:
            print(f"⚠ Generator failed: {e}")
            return {"answer": "Generation failed to parse.", "claims": []}
            
    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match: text = match.group(1)
        match2 = re.search(r'\{[\s\S]*\}', text)
        if match2: text = match2.group(0)
        return json.loads(text)
