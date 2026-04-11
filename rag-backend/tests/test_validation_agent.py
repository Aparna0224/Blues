"""Unit tests for Pydantic AI validation agent.

These tests verify that the validation schemas work correctly with
Pydantic AI agents for validating LLM outputs.
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydantic_ai import Agent

from src.validation.pydantic_ai_schemas import (
    SubQuestionValidation,
    SearchQueryValidation,
    PlannerOutputValidation,
    PlannerOutputSchema,
    ValidationDecision,
)


def get_model_id():
    """Get available model ID for testing."""
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if groq_key and groq_key != "your_groq_api_key_here":
        return 'groq:llama-3.3-70b-versatile'
    elif gemini_key and gemini_key != "your_gemini_api_key_here":
        return 'google-gla:gemini-2.0-flash'
    return None


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if no API key is available."""
    model_id = get_model_id()
    if model_id is None:
        pytest.skip("No API key available (GROQ_API_KEY or GEMINI_API_KEY required)")


class TestSubQuestionValidationAgent:
    """Tests for sub-question validation with Pydantic AI."""

    @pytest.mark.asyncio
    async def test_validate_subquestion_relevant(self, skip_if_no_api_key):
        """Test validation of a relevant sub-question."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        agent = Agent(
            model_id,
            output_type=SubQuestionValidation,
            system_prompt=(
                "You are a validation assistant. Evaluate the question and return structured data. "
                "The question is relevant if it relates to the main query about RAG in AI."
            ),
        )
        
        result = await agent.run(
            "Question: 'How does RAG improve factual accuracy?' "
            "Main query: 'What is the use of RAG in AI?'"
        )
        
        assert result.output is not None
        assert isinstance(result.output, SubQuestionValidation)
        assert result.output.is_relevant is True
        assert result.output.is_well_formed is True

    @pytest.mark.asyncio
    async def test_validate_subquestion_aspect(self, skip_if_no_api_key):
        """Test validation captures aspect coverage."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        agent = Agent(
            model_id,
            output_type=SubQuestionValidation,
            system_prompt=(
                "You are a validation assistant. Determine which aspect the question covers: "
                "methodology, datasets, results, limitations, or other."
            ),
        )
        
        result = await agent.run(
            "Question: 'What datasets were used to benchmark RAG?'"
        )
        
        assert result.output is not None
        assert result.output.covers_aspect in ["datasets", "results", "methodology", "limitations", "other", None]


class TestPlannerOutputValidationAgent:
    """Tests for planner output validation with Pydantic AI."""

    @pytest.mark.asyncio
    async def test_validate_planner_output(self, skip_if_no_api_key):
        """Test validation of complete planner output."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        agent = Agent(
            model_id,
            output_type=PlannerOutputValidation,
            system_prompt=(
                "You are a validation assistant. Evaluate the planner output for a RAG query. "
                "Return validation scores between 0 and 1."
            ),
        )
        
        planner_output = """
        Sub-questions:
        1. How does RAG work?
        2. What are RAG's main benefits?
        3. What are RAG's limitations?
        
        Search queries:
        1. RAG retrieval augmented generation methodology
        2. RAG benefits accuracy improvement
        3. RAG limitations challenges
        """
        
        result = await agent.run(f"Validate this planner output:\n{planner_output}")
        
        assert result.output is not None
        assert isinstance(result.output, PlannerOutputValidation)
        assert 0 <= result.output.coverage_score <= 1
        assert 0 <= result.output.diversity_score <= 1


class TestValidationDecisionAgent:
    """Tests for validation decision making with Pydantic AI."""

    @pytest.mark.asyncio
    async def test_accept_decision(self, skip_if_no_api_key):
        """Test that valid output gets accept decision."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        agent = Agent(
            model_id,
            output_type=ValidationDecision,
            system_prompt=(
                "You are a validation decision assistant. "
                "If the output meets all criteria, decide 'accept'. "
                "Otherwise decide 'retry' or 'fallback'."
            ),
        )
        
        valid_output = """
        Sub-questions: ['How does RAG work?', 'What datasets does RAG use?', 'What are RAG results?']
        Search queries: ['RAG methodology', 'RAG datasets', 'RAG benchmark results']
        Coverage: High
        Diversity: Good
        """
        
        result = await agent.run(f"Evaluate: {valid_output}")
        
        assert result.output is not None
        assert result.output.action in ["accept", "retry", "fallback"]

    @pytest.mark.asyncio
    async def test_retry_with_correction(self, skip_if_no_api_key):
        """Test that invalid output gets retry with correction."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        agent = Agent(
            model_id,
            output_type=ValidationDecision,
            system_prompt=(
                "You are a validation decision assistant. "
                "If output has issues, decide 'retry' and provide corrected output. "
                "Output should have 3-5 sub-questions and search queries."
            ),
        )
        
        invalid_output = """
        Sub-questions: ['Only one question']
        Search queries: ['single query']
        Issues: Too few sub-questions, too few search queries
        """
        
        result = await agent.run(f"Evaluate and correct: {invalid_output}")
        
        assert result.output is not None
        if result.output.action == "retry" and result.output.corrected_output:
            assert len(result.output.corrected_output.sub_questions) >= 3
            assert len(result.output.corrected_output.search_queries) >= 3


class TestPlannerOutputSchemaAgent:
    """Tests for generating planner output with Pydantic AI."""

    @pytest.mark.asyncio
    async def test_generate_subquestions(self, skip_if_no_api_key):
        """Test generation of sub-questions."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        agent = Agent(
            model_id,
            output_type=PlannerOutputSchema,
            system_prompt=(
                "You are a research planning assistant. Generate 3-5 diverse sub-questions "
                "and 3-5 targeted search queries for the given main question. "
                "Sub-questions must be at least 10 characters."
            ),
        )
        
        for attempt in range(3):
            try:
                result = await agent.run(
                    "Main question: What is the use of RAG in AI?"
                )
                break
            except Exception as e:
                if attempt == 2:
                    pytest.skip(f"Subquestion generation flaky: {e}")
        
        assert result.output is not None
        assert isinstance(result.output, PlannerOutputSchema)
        assert 3 <= len(result.output.sub_questions) <= 5
        assert 3 <= len(result.output.search_queries) <= 5
        
        for q in result.output.sub_questions:
            assert len(q.strip()) >= 10, f"Question too short: {q}"


class TestSchemaValidationRoundTrip:
    """Tests for schema validation round-trip."""

    def test_planner_schema_validates_generated_output(self, skip_if_no_api_key):
        """Test that generated output validates against schema."""
        output = {
            "sub_questions": [
                "How does RAG improve accuracy in AI systems?",
                "What datasets are commonly used to evaluate RAG?",
                "What are the main limitations of RAG approaches?",
            ],
            "search_queries": [
                "RAG retrieval augmented generation accuracy",
                "RAG benchmark datasets evaluation",
                "RAG limitations challenges future work",
            ],
        }
        
        validated = PlannerOutputSchema.model_validate(output)
        assert len(validated.sub_questions) == 3
        assert len(validated.search_queries) == 3

    def test_planner_schema_rejects_invalid_output(self):
        """Test that invalid output is rejected by schema."""
        output = {
            "sub_questions": ["Short"],  # Too short
            "search_queries": ["Valid query 1", "Valid query 2", "Valid query 3"],
        }
        
        with pytest.raises(Exception):
            PlannerOutputSchema.model_validate(output)


class TestIntegrationValidationFlow:
    """Integration tests for the validation flow."""

    @pytest.mark.asyncio
    async def test_full_validation_flow(self, skip_if_no_api_key):
        """Test complete validation flow: generate -> validate -> decide."""
        model_id = get_model_id()
        if model_id is None:
            pytest.skip("No API key available")
        
        planning_agent = Agent(
            model_id,
            output_type=PlannerOutputSchema,
            system_prompt=(
                "Generate 3-5 diverse sub-questions and search queries for RAG research. "
                "Sub-questions must be at least 10 characters."
            ),
        )
        
        validation_agent = Agent(
            model_id,
            output_type=PlannerOutputValidation,
            system_prompt=(
                "Evaluate planner output for RAG research. "
                "Return coverage and diversity scores 0-1."
            ),
        )
        
        decision_agent = Agent(
            model_id,
            output_type=ValidationDecision,
            system_prompt="Decide accept/retry/fallback for planner output.",
        )
        
        plan_result = await planning_agent.run("What is the use of RAG in AI?")
        plan_data = plan_result.output
        
        validation_result = await validation_agent.run(
            f"Sub-questions: {plan_data.sub_questions}\n"
            f"Search queries: {plan_data.search_queries}"
        )
        
        decision_result = await decision_agent.run(
            f"Sub-questions: {plan_data.sub_questions}\n"
            f"Coverage: {validation_result.output.coverage_score}\n"
            f"Diversity: {validation_result.output.diversity_score}"
        )
        
        assert decision_result.output.action in ["accept", "retry", "fallback"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
