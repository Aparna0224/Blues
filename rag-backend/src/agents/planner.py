"""Agentic Planner for LangGraph. STRICT diversity requirements."""
import json
import re
from typing import Dict, Any, List
from src.llm.base import BaseLLM

class PlannerAgent:
    """
    Planner Node for generating exactly 3-5 diverse sub-questions
    and 3-5 targeted search queries focusing on specific aspects.
    """
    
    SYSTEM_PROMPT = """
You are a master academic planner orchestrating an Agentic RAG pipeline.
Your task is to take the User Query and generate a STRICT exploration plan.

RULES:
1. Generate EXACTLY 3-5 sub-questions.
2. Generate EXACTLY 3-5 search queries.
3. DIVERSITY: You MUST generate queries targeting different fundamental aspects. 
   Ensure you cover:
   - Methodology / Architecture
   - Datasets / Benchmarks
   - Results / Accuracy
   - Limitations / Open Problems
4. SPECIFICITY: Do not use generic words. Make search queries 3-7 keywords max.
5. NO token overlap filtering or over-constraining. Let the questions naturally diverge.

OUTPUT FORMAT (Valid JSON only):
{
  "sub_questions": [
    "...", "...", "..."
  ],
  "search_queries": [
    "...", "...", "..."
  ]
}
"""

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        
    def plan(self, query: str) -> Dict[str, List[str]]:
        """Decomposes the query according to strict system instructions."""
        print(f"🧠 [PlannerNode] Decomposing query: '{query}'")
        
        prompt = f"{self.SYSTEM_PROMPT}\nUser Query: {query}\nOutput JSON:"
        
        try:
            raw = self.llm.generate(prompt)
            parsed = self._parse_json(raw)
            
            sq = parsed.get("sub_questions", [])
            sq_search = parsed.get("search_queries", [])
            
            # Enforce constraints
            if len(sq) < 3:
                sq.extend([f"What methodology is applied for {query}?", f"What datasets are evaluated for {query}?"])
            if len(sq_search) < 3:
                sq_search.extend([f"{query} methodology architecture", f"{query} dataset benchmark evaluation"])
                
            return {
                "sub_questions": sq[:5],
                "search_queries": sq_search[:5]
            }
            
        except Exception as e:
            print(f"⚠ Planner failed: {e}")
            # Fallback
            return {
                "sub_questions": [
                    f"What is the core methodology of {query}?",
                    f"What datasets are used to train or evaluate {query}?",
                    f"What are the results and limitations of {query}?"
                ],
                "search_queries": [
                    f"{query} methodology approach",
                    f"{query} datasets benchmarks",
                    f"{query} results limitations"
                ]
            }
            
    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match: text = match.group(1)
        match2 = re.search(r'\{[\s\S]*\}', text)
        if match2: text = match2.group(0)
        return json.loads(text)
