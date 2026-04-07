"""Planner Agent for query decomposition."""

import json
import re
from typing import Dict, Any, List, Optional
from src.llm.base import BaseLLM


class PlannerAgent:
    """
    Planner Agent for Stage 3 Agentic RAG.
    
    Decomposes complex research queries into:
    - Sub-questions (2-4)
    - Search queries (2-4)
    
    Does NOT:
    - Retrieve
    - Rank
    - Verify
    - Refine
    
    It only plans.
    """
    
    PLANNER_PROMPT = """You are a research planning agent.

Your task is to decompose a research question into structured sub-questions and search queries.

Rules:
1. Generate 2-4 sub-questions that break down the main question
2. Generate 2-4 search queries optimized for academic paper retrieval
3. Search queries should be keyword-focused, not full sentences
4. Return ONLY valid JSON, no explanations

Input Question:
{question}

Return this exact JSON structure:
{{
  "main_question": "the original question",
  "sub_questions": [
    "sub-question 1",
    "sub-question 2"
  ],
  "search_queries": [
    "search query 1",
    "search query 2"
  ]
}}

JSON Output:"""

    LEVEL_GUIDANCE = {
        "beginner": "Include definitions, basics, and conceptual overview before methods.",
        "intermediate": "Focus on methods, datasets, and practical applications. Avoid unrelated background context.",
        "advanced": "Focus on benchmarks, limitations, comparisons, and research gaps. Avoid introductory background.",
    }

    INTENT_KEYWORDS = {
        "dataset": ["dataset", "datasets", "data", "benchmark", "corpus", "collection", "samples"],
        "detection": ["detect", "detection", "identify", "mitigate", "mitigation", "prevent"],
        "types": ["type", "types", "category", "categories", "taxonomy", "class"],
        "methodology": ["method", "approach", "pipeline", "framework", "technique", "constructed"],
    }

    # ── Comparison-aware planning (Phase 1) ──────────────────────

    COMPARISON_SEARCH_SUFFIXES = [
        "{topic} dataset benchmark evaluation",
        "{topic} methodology approach architecture",
        "{topic} accuracy results performance metrics",
    ]

    MANDATORY_COMPARISON_TEMPLATES = [
        "What datasets or benchmark corpora does each paper use for training and evaluation of {topic}?",
        "What are the core methodological steps, model architectures, or algorithmic approaches proposed by each paper on {topic}?",
        "What quantitative results, accuracy metrics, or performance benchmarks does each paper report for {topic}?",
    ]

    def __init__(self, llm: BaseLLM):
        """
        Initialize PlannerAgent.
        
        Args:
            llm: LLM instance (LocalLLM or GeminiLLM)
        """
        self.llm = llm
    
    def detect_user_level(self, query: str) -> str:
        q = (query or "").lower()
        beginner_cues = ["what is", "basic", "basics", "overview", "introduction", "for beginners"]
        advanced_cues = ["benchmark", "sota", "state of the art", "research gap", "limitation", "comparative"]

        if any(c in q for c in beginner_cues):
            return "beginner"
        if any(c in q for c in advanced_cues):
            return "advanced"
        return "intermediate"

    def resolve_user_level(self, query: str, user_level: str = "auto") -> str:
        requested = (user_level or "auto").strip().lower()
        if requested in {"beginner", "intermediate", "advanced"}:
            return requested
        return self.detect_user_level(query)

    def _classify_subquestion_intent(self, sub_question: str) -> str:
        sq = (sub_question or "").lower()
        for intent, keys in self.INTENT_KEYWORDS.items():
            if any(k in sq for k in keys):
                return intent
        return "methodology"

    @staticmethod
    def _extract_topic_keywords(question: str, top_n: int = 3) -> str:
        """Extract top N non-stopword keywords from the question as a topic phrase."""
        stop_words = {
            "what", "how", "why", "when", "where", "which", "is", "are",
            "does", "do", "can", "the", "a", "an", "in", "of", "and", "or",
            "to", "for", "on", "with", "by", "from", "as", "at", "about",
            "into", "be", "this", "that", "it", "its", "their", "they",
            "using", "used", "use", "each", "paper", "papers",
        }
        words = question.lower().replace("?", "").split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return " ".join(keywords[:top_n])

    def _prune_background_subquestions(self, sub_questions: List[str], resolved_level: str, main_question: str) -> List[str]:
        if resolved_level not in {"intermediate", "advanced"}:
            return sub_questions

        main_q = (main_question or "").lower()
        allow_background = any(k in main_q for k in ["overview", "introduction", "what is", "basics"])
        if allow_background:
            return sub_questions

        filtered = []
        for sq in sub_questions:
            low = (sq or "").lower()
            if any(k in low for k in ["what is", "introduction", "overview", "iot", "blockchain basics", "general background"]):
                continue
            filtered.append(sq)
        return filtered or sub_questions

    def _dataset_focused_plan(self, question: str, resolved_level: str) -> Optional[Dict[str, Any]]:
        q = (question or "").lower()
        if "dataset" not in q:
            return None

        if resolved_level == "beginner":
            sub_questions = [
                f"What is meant by a vulnerability dataset for {question}?",
                f"What kinds of information are typically included in {question}?",
                f"How are these datasets used in practice?",
            ]
            search_queries = [
                f"{question} definition",
                f"{question} schema fields",
                f"{question} practical use",
            ]
        else:
            sub_questions = [
                f"What datasets exist for {question}?",
                f"How are these datasets constructed and labeled?",
                f"What limitations and benchmark gaps exist in these datasets?",
            ]
            search_queries = [
                f"{question} benchmark datasets",
                f"{question} dataset construction labeling",
                f"{question} dataset limitations benchmark gaps",
            ]

        return {
            "main_question": question,
            "sub_questions": sub_questions,
            "search_queries": search_queries,
        }

    def plan(self, question: str, user_level: str = "auto") -> Dict[str, Any]:
        """
        Decompose a question into sub-questions and search queries.
        
        Args:
            question: User's research question
            
        Returns:
            Dictionary with:
            - main_question: str
            - sub_questions: List[str]
            - search_queries: List[str]
        """
        resolved_level = self.resolve_user_level(question, user_level)

        hand_plan = self._dataset_focused_plan(question, resolved_level)
        if hand_plan is not None:
            hand_plan["resolved_user_level"] = resolved_level
            hand_plan["subquestion_intents"] = {
                sq: self._classify_subquestion_intent(sq)
                for sq in hand_plan.get("sub_questions", [])
            }
            return hand_plan

        level_prompt = (
            f"\n\nResearch level: {resolved_level}\n"
            f"Guidance: {self.LEVEL_GUIDANCE.get(resolved_level, self.LEVEL_GUIDANCE['intermediate'])}\n"
            "Do not include unrelated background topics unless explicitly asked by the query."
        )
        prompt = self.PLANNER_PROMPT.format(question=question + level_prompt)
        
        print(f"🧠 Planning query decomposition...")
        
        try:
            raw_output = self.llm.generate(prompt)
            plan = self._parse_json(raw_output)
            
            # Validate plan structure
            plan = self._validate_plan(plan, question)
            plan["sub_questions"] = self._prune_background_subquestions(
                plan.get("sub_questions", []),
                resolved_level,
                question,
            )
            plan["resolved_user_level"] = resolved_level
            plan["subquestion_intents"] = {
                sq: self._classify_subquestion_intent(sq)
                for sq in plan.get("sub_questions", [])
            }
            
            print(f"✓ Generated plan with {len(plan['sub_questions'])} sub-questions")
            print(f"✓ Generated {len(plan['search_queries'])} search queries")

            # ── Inject comparison-aware sub-questions & queries ───
            plan = self._inject_comparison_plan(plan, question)

            return plan
            
        except Exception as e:
            print(f"⚠ Planning failed: {e}")
            # Fallback: return simple plan with original query
            fallback = self._fallback_plan(question)
            fallback["resolved_user_level"] = resolved_level
            fallback["subquestion_intents"] = {
                sq: self._classify_subquestion_intent(sq)
                for sq in fallback.get("sub_questions", [])
            }
            fallback = self._inject_comparison_plan(fallback, question)
            return fallback
    
    def _parse_json(self, raw_output: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM output.
        
        Handles common issues like markdown code blocks, extra text.
        
        Args:
            raw_output: Raw LLM response
            
        Returns:
            Parsed dictionary
        """
        # Remove markdown code blocks if present
        text = raw_output.strip()
        
        # Try to find JSON in the output
        # Pattern 1: ```json ... ```
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)
        
        # Pattern 2: Look for { ... } directly
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            text = brace_match.group(0)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}\nRaw output: {raw_output[:500]}")
    
    def _validate_plan(self, plan: Dict[str, Any], original_question: str) -> Dict[str, Any]:
        """
        Validate and fix plan structure.
        
        Args:
            plan: Parsed plan dictionary
            original_question: Original user question
            
        Returns:
            Validated plan
        """
        # Ensure main_question exists
        if "main_question" not in plan or not plan["main_question"]:
            plan["main_question"] = original_question
        
        # Ensure sub_questions exists and has content
        if "sub_questions" not in plan or not plan["sub_questions"]:
            plan["sub_questions"] = [original_question]
        
        # Ensure search_queries exists and has content
        if "search_queries" not in plan or not plan["search_queries"]:
            # Generate simple search queries from question
            plan["search_queries"] = self._extract_search_queries(original_question)
        
        # Limit to 4 max
        plan["sub_questions"] = plan["sub_questions"][:4]
        plan["search_queries"] = plan["search_queries"][:4]
        
        return plan
    
    def _extract_search_queries(self, question: str) -> List[str]:
        """
        Extract simple search queries from question (fallback).
        
        Args:
            question: User question
            
        Returns:
            List of search query strings
        """
        # Remove common question words
        stop_words = {"what", "how", "why", "when", "where", "which", "is", "are", 
                      "does", "do", "can", "the", "a", "an", "in", "of", "and", "or"}
        
        words = question.lower().replace("?", "").split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        if len(keywords) >= 4:
            return [
                " ".join(keywords[:3]),
                " ".join(keywords[1:4]),
                " ".join(keywords)
            ]
        else:
            return [" ".join(keywords)]
    
    def _fallback_plan(self, question: str) -> Dict[str, Any]:
        """
        Generate fallback plan when LLM fails.
        
        Args:
            question: Original question
            
        Returns:
            Simple plan dictionary
        """
        search_queries = self._extract_search_queries(question)
        
        return {
            "main_question": question,
            "sub_questions": [question],
            "search_queries": search_queries
        }
    
    def format_plan(self, plan: Dict[str, Any]) -> str:
        """
        Format plan for display.
        
        Args:
            plan: Plan dictionary
            
        Returns:
            Formatted string
        """
        output = []
        output.append("=" * 78)
        output.append("QUERY DECOMPOSITION PLAN")
        output.append("=" * 78)
        output.append(f"\nMain Question: {plan['main_question']}\n")
        
        output.append("Sub-Questions:")
        for i, sq in enumerate(plan["sub_questions"], 1):
            output.append(f"  {i}. {sq}")
        
        output.append("\nSearch Queries:")
        for i, sq in enumerate(plan["search_queries"], 1):
            output.append(f"  {i}. \"{sq}\"")
        
        output.append("")
        return "\n".join(output)

    def _inject_comparison_plan(
        self, plan: Dict[str, Any], question: str,
    ) -> Dict[str, Any]:
        """Append mandatory comparison sub-questions and search queries.

        Always injects three axes: dataset, methodology, results.
        Limits total sub-questions to 7 and search queries to 7.
        Adds ``comparison_axes`` key to the plan dict.
        """
        topic = self._extract_topic_keywords(question)
        if not topic:
            topic = question[:60]

        # Append comparison sub-questions (deduplicate against existing)
        existing_sq_lower = {sq.lower() for sq in plan.get("sub_questions", [])}
        for template in self.MANDATORY_COMPARISON_TEMPLATES:
            cq = template.format(topic=topic)
            if cq.lower() not in existing_sq_lower:
                plan.setdefault("sub_questions", []).append(cq)
                existing_sq_lower.add(cq.lower())

        # Append comparison search queries
        existing_srch_lower = {sq.lower() for sq in plan.get("search_queries", [])}
        for suffix in self.COMPARISON_SEARCH_SUFFIXES:
            csq = suffix.format(topic=topic)
            if csq.lower() not in existing_srch_lower:
                plan.setdefault("search_queries", []).append(csq)
                existing_srch_lower.add(csq.lower())

        # Cap to reasonable limits
        plan["sub_questions"] = plan["sub_questions"][:7]
        plan["search_queries"] = plan["search_queries"][:7]

        # Update intents map for new sub-questions
        plan["subquestion_intents"] = {
            sq: self._classify_subquestion_intent(sq)
            for sq in plan.get("sub_questions", [])
        }

        # Mark comparison axes
        plan["comparison_axes"] = ["dataset", "methodology", "results"]

        print(f"✓ Injected comparison plan: {len(plan['sub_questions'])} sub-Qs, {len(plan['search_queries'])} search queries")
        return plan
