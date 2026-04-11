"""Pydantic AI validators for pipeline output validation.

This module defines structured validation models using Pydantic AI
to evaluate LLM outputs at critical pipeline stages.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SubQuestionValidation(BaseModel):
    """Individual sub-question validation result."""
    question: str
    is_relevant: bool = Field(description="Does this question relate to the main query?")
    covers_aspect: Optional[str] = Field(
        default=None,
        description="Which aspect does this cover? methodology|datasets|results|limitations|other"
    )
    is_well_formed: bool = Field(description="Is this a proper question?")
    is_diverse: bool = Field(description="Is this sufficiently different from other questions?")


class SearchQueryValidation(BaseModel):
    """Individual search query validation result."""
    query: str
    is_specific: bool = Field(description="Is this query specific (3-7 keywords)?")
    is_valid: bool = Field(description="Is this a valid search query?")
    covers_aspect: Optional[str] = Field(
        default=None,
        description="Which aspect does this target?"
    )


class PlannerOutputValidation(BaseModel):
    """Validation result for PlannerAgent output."""
    is_valid: bool = Field(description="Overall validity of the planner output")
    sub_questions_valid: list[SubQuestionValidation] = Field(
        description="Validation results for each sub-question"
    )
    search_queries_valid: list[SearchQueryValidation] = Field(
        description="Validation results for each search query"
    )
    coverage_score: float = Field(
        description="Score 0-1 for coverage of required aspects",
        ge=0.0,
        le=1.0
    )
    diversity_score: float = Field(
        description="Score 0-1 for diversity of sub-questions",
        ge=0.0,
        le=1.0
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of identified issues"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )


class PlannerOutputSchema(BaseModel):
    """Expected output schema for PlannerAgent."""
    sub_questions: list[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-5 diverse sub-questions covering different aspects"
    )
    search_queries: list[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-5 targeted search queries"
    )

    @field_validator('sub_questions')
    @classmethod
    def validate_sub_questions_not_empty(cls, v):
        for q in v:
            if not q.strip():
                raise ValueError("Sub-question cannot be empty or whitespace only")
            if len(q.strip()) < 10:
                raise ValueError(f"Sub-question too short: '{q}'")
        return v

    @field_validator('search_queries')
    @classmethod
    def validate_search_queries_not_empty(cls, v):
        for q in v:
            if not q.strip():
                raise ValueError("Search query cannot be empty or whitespace only")
        return v


class ValidationDecision(BaseModel):
    """Decision on how to handle validation result."""
    action: str = Field(
        description="Action to take: accept|retry|fallback"
    )
    reason: str = Field(
        description="Reason for the decision"
    )
    corrected_output: Optional[PlannerOutputSchema] = Field(
        default=None,
        description="Corrected output if action is retry or fallback"
    )
