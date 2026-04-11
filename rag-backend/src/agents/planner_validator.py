"""Planner Validator Agent using Pydantic AI for semantic validation.

Validates PlannerAgent output for:
- Relevance to main query
- Coverage of required aspects (methodology, datasets, results, limitations)
- Diversity of sub-questions
- Quality of search queries
"""

import os
from typing import Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai import AgentRunResult

from src.validation.pydantic_ai_schemas import (
    PlannerOutputValidation,
    PlannerOutputSchema,
    ValidationDecision,
    SubQuestionValidation,
    SearchQueryValidation,
)


SYSTEM_PROMPT = """You are an expert academic research validator. Your task is to validate the output of a query planning agent.

STRICT RULES:
1. Evaluate each sub-question for:
   - Relevance: Does it relate to the main query?
   - Coverage: Does it cover a required aspect (methodology, datasets, results, limitations)?
   - Well-formedness: Is it a proper question?
   - Diversity: Is it different from other questions?

2. Evaluate each search query for:
   - Specificity: Is it 3-7 keywords?
   - Validity: Is it a proper search query?
   - Coverage: What aspect does it target?

3. Calculate coverage and diversity scores (0-1).

4. Provide actionable recommendations for improvement.

Return your validation in the exact JSON format specified.
"""


class PlannerValidatorAgent:
    """
    Pydantic AI agent for validating PlannerAgent output.
    
    Uses LLM-as-judge to perform semantic validation of:
    - Sub-question relevance and coverage
    - Search query quality
    - Overall diversity and coverage
    """
    
    def __init__(self, model: Optional[str] = None):
        if model:
            model_name = model
        elif os.getenv("VALIDATION_MODEL"):
            model_name = os.getenv("VALIDATION_MODEL")
        else:
            provider = os.getenv("LLM_PROVIDER", "groq")
            if provider == "groq":
                model_name = f"groq:{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}"
            elif provider == "gemini":
                model_name = f"gemini-gla:{os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}"
            else:
                model_name = "openai:gpt-4o-mini"

        self._agent = Agent(
            model=model_name,
            output_type=PlannerOutputValidation,
            system_prompt=SYSTEM_PROMPT,
        )
    
    async def validate(
        self,
        main_query: str,
        planner_output: dict,
    ) -> tuple[PlannerOutputValidation, ValidationDecision]:
        """
        Validate the planner output using Pydantic AI.
        
        Args:
            main_query: The original user query
            planner_output: Dict with 'sub_questions' and 'search_queries'
            
        Returns:
            Tuple of (validation_result, decision)
        """
        sub_questions = planner_output.get("sub_questions", [])
        search_queries = planner_output.get("search_queries", [])
        
        user_prompt = self._build_validation_prompt(main_query, sub_questions, search_queries)
        
        try:
            result: AgentRunResult[PlannerOutputValidation] = await self._agent.run(user_prompt)
            validation = result.output
            decision = self._make_decision(validation, planner_output)
            return validation, decision
            
        except Exception as e:
            print(f"⚠ Pydantic AI validation failed: {e}")
            return self._fallback_validation(str(e)), self._fallback_decision(planner_output)
    
    def _build_validation_prompt(
        self,
        main_query: str,
        sub_questions: list[str],
        search_queries: list[str],
    ) -> str:
        """Build the validation prompt."""
        sq_list = "\n".join(f"- {sq}" for sq in sub_questions)
        sq_queries = "\n".join(f"- {q}" for q in search_queries)
        
        return f"""MAIN QUERY: {main_query}

SUB-QUESTIONS TO VALIDATE:
{sq_list}

SEARCH QUERIES TO VALIDATE:
{sq_queries}

Required aspects to cover: methodology, datasets, results, limitations

Return validation in this JSON format:
{{
  "is_valid": true/false,
  "sub_questions_valid": [
    {{
      "question": "...",
      "is_relevant": true/false,
      "covers_aspect": "methodology|datasets|results|limitations|other",
      "is_well_formed": true/false,
      "is_diverse": true/false
    }}
  ],
  "search_queries_valid": [
    {{
      "query": "...",
      "is_specific": true/false,
      "is_valid": true/false,
      "covers_aspect": "methodology|datasets|results|limitations/other"
    }}
  ],
  "coverage_score": 0.0-1.0,
  "diversity_score": 0.0-1.0,
  "issues": ["issue1", "issue2"],
  "recommendations": ["recommendation1", "recommendation2"]
}}"""

    def _make_decision(
        self,
        validation: PlannerOutputValidation,
        original_output: dict,
    ) -> ValidationDecision:
        """Make a decision based on validation result."""
        issues = validation.issues
        
        if validation.is_valid and validation.coverage_score >= 0.6:
            return ValidationDecision(
                action="accept",
                reason="Planner output is valid with good coverage and diversity"
            )
        
        if len(issues) <= 2 and validation.coverage_score >= 0.4:
            corrected = self._generate_corrected_output(validation, original_output)
            return ValidationDecision(
                action="retry",
                reason=f"Minor issues found: {'; '.join(issues[:2])}",
                corrected_output=corrected
            )
        
        return ValidationDecision(
            action="fallback",
            reason=f"Significant issues: {'; '.join(issues[:3])}",
            corrected_output=self._generate_fallback_output(original_output)
        )
    
    def _generate_corrected_output(
        self,
        validation: PlannerOutputValidation,
        original: dict,
    ) -> PlannerOutputSchema:
        """Generate corrected output based on validation."""
        valid_sqs = [
            sqv.question for sqv in validation.sub_questions_valid
            if sqv.is_relevant and sqv.is_well_formed
        ]
        valid_queries = [
            qv.query for qv in validation.search_queries_valid
            if qv.is_valid and qv.is_specific
        ]
        
        main_query = original.get("main_query", "")
        
        if len(valid_sqs) >= 3:
            sub_questions = valid_sqs[:5]
        else:
            sub_questions = valid_sqs + self._fill_missing_sqs(main_query, 3 - len(valid_sqs))
        
        if len(valid_queries) >= 3:
            search_queries = valid_queries[:5]
        else:
            search_queries = valid_queries + self._fill_missing_queries(main_query, 3 - len(valid_queries))
        
        return PlannerOutputSchema(
            sub_questions=sub_questions,
            search_queries=search_queries
        )
    
    def _generate_fallback_output(self, original: dict) -> PlannerOutputSchema:
        """Generate fallback output when validation completely fails."""
        main_query = original.get("main_query", original.get("query", ""))
        return PlannerOutputSchema(
            sub_questions=[
                f"What is the methodology or approach used in {main_query}?",
                f"What datasets or benchmarks are used for {main_query}?",
                f"What are the results and performance of {main_query}?",
            ],
            search_queries=[
                f"{main_query} methodology approach",
                f"{main_query} datasets benchmarks",
                f"{main_query} results evaluation",
            ]
        )
    
    def _fill_missing_sqs(self, query: str, count: int) -> list[str]:
        """Generate additional sub-questions to fill gaps."""
        templates = [
            f"What are the limitations or challenges of {query}?",
            f"How does {query} compare to existing methods?",
            f"What are the future research directions for {query}?",
        ]
        return templates[:count]
    
    def _fill_missing_queries(self, query: str, count: int) -> list[str]:
        """Generate additional search queries to fill gaps."""
        templates = [
            f"{query} limitations challenges",
            f"{query} comparison baseline",
            f"{query} future work direction",
        ]
        return templates[:count]
    
    def _fallback_validation(self, error: str) -> PlannerOutputValidation:
        """Return a fallback validation result on error."""
        return PlannerOutputValidation(
            is_valid=False,
            sub_questions_valid=[],
            search_queries_valid=[],
            coverage_score=0.0,
            diversity_score=0.0,
            issues=[f"Validation error: {error}"],
            recommendations=["Use fallback planner output"]
        )
    
    def _fallback_decision(self, original: dict) -> ValidationDecision:
        """Return a fallback decision on error."""
        return ValidationDecision(
            action="fallback",
            reason="Pydantic AI validation failed, using original output",
            corrected_output=self._generate_fallback_output(original)
        )


def create_planner_validator() -> PlannerValidatorAgent:
    """Factory function to create a PlannerValidatorAgent."""
    return PlannerValidatorAgent()
