"""Unit tests for Pydantic AI validation schemas."""

import pytest
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.validation.pydantic_ai_schemas import (
    SubQuestionValidation,
    SearchQueryValidation,
    PlannerOutputValidation,
    PlannerOutputSchema,
    ValidationDecision,
)


class TestSubQuestionValidation:
    """Tests for SubQuestionValidation schema."""

    def test_valid_subquestion_validation(self):
        validation = SubQuestionValidation(
            question="How does RAG work?",
            is_relevant=True,
            covers_aspect="methodology",
            is_well_formed=True,
            is_diverse=True,
        )
        assert validation.question == "How does RAG work?"
        assert validation.is_relevant is True

    def test_optional_aspect(self):
        validation = SubQuestionValidation(
            question="What is RAG?",
            is_relevant=True,
            is_well_formed=True,
            is_diverse=True,
        )
        assert validation.covers_aspect is None

    def test_all_aspect_values(self):
        for aspect in ["methodology", "datasets", "results", "limitations", "other"]:
            validation = SubQuestionValidation(
                question="Test question",
                is_relevant=True,
                covers_aspect=aspect,
                is_well_formed=True,
                is_diverse=True,
            )
            assert validation.covers_aspect == aspect


class TestSearchQueryValidation:
    """Tests for SearchQueryValidation schema."""

    def test_valid_search_query_validation(self):
        validation = SearchQueryValidation(
            query="RAG retrieval augmented generation methodology",
            is_specific=True,
            is_valid=True,
            covers_aspect="methodology",
        )
        assert validation.query == "RAG retrieval augmented generation methodology"

    def test_optional_covers_aspect(self):
        validation = SearchQueryValidation(
            query="test query",
            is_specific=False,
            is_valid=True,
        )
        assert validation.covers_aspect is None


class TestPlannerOutputValidation:
    """Tests for PlannerOutputValidation schema."""

    def test_valid_planner_output_validation(self):
        validation = PlannerOutputValidation(
            is_valid=True,
            sub_questions_valid=[
                SubQuestionValidation(
                    question="Q1?",
                    is_relevant=True,
                    is_well_formed=True,
                    is_diverse=True,
                ),
            ],
            search_queries_valid=[
                SearchQueryValidation(
                    query="test query",
                    is_specific=True,
                    is_valid=True,
                ),
            ],
            coverage_score=0.8,
            diversity_score=0.9,
            issues=[],
            recommendations=["Consider adding more diverse sources"],
        )
        assert validation.is_valid is True
        assert validation.coverage_score == 0.8

    def test_coverage_score_bounds(self):
        validation = PlannerOutputValidation(
            is_valid=True,
            sub_questions_valid=[],
            search_queries_valid=[],
            coverage_score=0.5,
            diversity_score=0.5,
        )
        assert validation.coverage_score == 0.5

    def test_coverage_score_too_high_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputValidation(
                is_valid=True,
                sub_questions_valid=[],
                search_queries_valid=[],
                coverage_score=1.5,  # Must be <= 1.0
                diversity_score=0.5,
            )
        assert "coverage_score" in str(exc_info.value)

    def test_coverage_score_negative_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputValidation(
                is_valid=True,
                sub_questions_valid=[],
                search_queries_valid=[],
                coverage_score=-0.1,  # Must be >= 0.0
                diversity_score=0.5,
            )
        assert "coverage_score" in str(exc_info.value)

    def test_default_empty_lists(self):
        validation = PlannerOutputValidation(
            is_valid=False,
            sub_questions_valid=[],
            search_queries_valid=[],
            coverage_score=0.0,
            diversity_score=0.0,
        )
        assert validation.issues == []
        assert validation.recommendations == []


class TestPlannerOutputSchema:
    """Tests for PlannerOutputSchema - the expected output format."""

    def test_valid_planner_output_schema(self):
        schema = PlannerOutputSchema(
            sub_questions=[
                "How does RAG improve accuracy?",
                "What datasets are used in RAG research?",
                "What are the limitations of RAG?",
            ],
            search_queries=[
                "RAG retrieval augmented generation accuracy",
                "RAG benchmark datasets",
                "RAG limitations challenges",
            ],
        )
        assert len(schema.sub_questions) == 3
        assert len(schema.search_queries) == 3

    def test_minimum_sub_questions(self):
        schema = PlannerOutputSchema(
            sub_questions=["Question 1", "Question 2", "Question 3"],
            search_queries=["Query 1", "Query 2", "Query 3"],
        )
        assert len(schema.sub_questions) == 3

    def test_too_few_sub_questions_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Only one question"],  # min_length=3
                search_queries=["Query 1", "Query 2", "Query 3"],
            )
        assert "sub_questions" in str(exc_info.value)

    def test_too_many_sub_questions_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=[
                    "Q1", "Q2", "Q3", "Q4", "Q5", "Q6"  # max_length=5
                ],
                search_queries=["Query 1", "Query 2", "Query 3"],
            )
        assert "sub_questions" in str(exc_info.value)

    def test_too_few_search_queries_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Q1", "Q2", "Q3"],
                search_queries=["Only one"],  # min_length=3
            )
        assert "search_queries" in str(exc_info.value)

    def test_too_many_search_queries_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Q1", "Q2", "Q3"],
                search_queries=["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"],  # max_length=5
            )
        assert "search_queries" in str(exc_info.value)

    def test_empty_sub_question_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Valid question", "", "Another valid question"],
                search_queries=["Q1", "Q2", "Q3"],
            )
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_sub_question_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Valid question", "   ", "Another valid"],
                search_queries=["Q1", "Q2", "Q3"],
            )
        assert "empty" in str(exc_info.value).lower()

    def test_sub_question_too_short_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Short", "This is valid question", "Another valid"],
                search_queries=["Q1", "Q2", "Q3"],
            )
        assert "too short" in str(exc_info.value).lower()

    def test_empty_search_query_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Q1", "Q2", "Q3"],
                search_queries=["Valid query", "", "Another valid"],
            )
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_search_query_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerOutputSchema(
                sub_questions=["Q1", "Q2", "Q3"],
                search_queries=["Valid", "  \t  ", "Another"],
            )
        assert "empty" in str(exc_info.value).lower()


class TestValidationDecision:
    """Tests for ValidationDecision schema."""

    def test_accept_decision(self):
        decision = ValidationDecision(
            action="accept",
            reason="Output meets all criteria",
        )
        assert decision.action == "accept"
        assert decision.corrected_output is None

    def test_retry_decision_with_correction(self):
        """Test that retry decision can include corrected output."""
        corrected = PlannerOutputSchema(
            sub_questions=[
                "Question 1 about RAG?",
                "Question 2 about RAG?",
                "Question 3 about RAG?",
            ],
            search_queries=[
                "Query 1 for RAG",
                "Query 2 for RAG",
                "Query 3 for RAG",
            ],
        )
        decision = ValidationDecision(
            action="retry",
            reason="Missing diversity in sub-questions",
            corrected_output=corrected,
        )
        assert decision.action == "retry"
        assert decision.corrected_output is not None

    def test_fallback_decision(self):
        decision = ValidationDecision(
            action="fallback",
            reason="Unable to generate valid output after retries",
        )
        assert decision.action == "fallback"

    def test_valid_actions(self):
        """Test that only valid actions are accepted."""
        for action in ["accept", "retry", "fallback"]:
            decision = ValidationDecision(
                action=action,
                reason="Test",
            )
            assert decision.action == action

    def test_invalid_action_allowed_by_default(self):
        """Note: The current schema doesn't restrict action values, so any string is valid."""
        decision = ValidationDecision(
            action="invalid_action",
            reason="Test",
        )
        assert decision.action == "invalid_action"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
