"""Pydantic models for LLM output validation."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class EvidenceUnit(BaseModel):
    """Evidence unit with citation and metadata."""
    chunk_id: str
    section: str
    location_start: int
    location_end: int
    relevance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)   
    confidence_band: str
    text: str = Field(min_length=1)
    paper_id: Optional[str] = None
    paper_title: Optional[str] = None
    paper_year: Optional[str] = None
    subquery_similarity: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Evidence text cannot be empty')
        return v.strip()


class PaperEvidence(BaseModel):
    """Evidence grouped by paper."""
    paper_id: str
    paper_title: str = Field(min_length=1)
    paper_year: Optional[str] = None
    doi: Optional[str] = None
    link: Optional[str] = None
    evidence_units: List[EvidenceUnit] = Field(default_factory=list)

    @field_validator('evidence_units')
    @classmethod
    def validate_evidence_units(cls, v: List[EvidenceUnit]) -> List[EvidenceUnit]:
        if not v:
            raise ValueError('Paper must have at least one evidence unit')
        return v


class ConflictAnalysis(BaseModel):
    """Conflict analysis between papers."""
    claim_a: str
    claim_b: str
    type: str
    strength: float = Field(ge=0.0, le=1.0)
    explanation: str


class SubQuestionAnalysis(BaseModel):
    """Analysis for a single sub-question."""
    question: str = Field(min_length=1)
    intent: Optional[str] = None
    papers: List[PaperEvidence] = Field(default_factory=list)
    conflicts: List[ConflictAnalysis] = Field(default_factory=list)
    comparison_text: Optional[str] = None
    mini_summary: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None


class PlanningInfo(BaseModel):
    """Planning information from the agent."""
    main_question: str = Field(min_length=1)
    sub_questions: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    """Verification result from Stage 4."""
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence_band: Optional[str] = None
    papers_verified: int = Field(default=0, ge=0)
    claims_verified: int = Field(default=0, ge=0)
    claims_supported: int = Field(default=0, ge=0)
    claims_contradicted: int = Field(default=0, ge=0)
    evidence_sources: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    audit: Dict[str, Any] = Field(default_factory=dict)


class PaperInfo(BaseModel):
    """Paper metadata."""
    paper_id: str
    title: str = Field(min_length=1)
    authors: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    source: Optional[str] = None


class GroupedAnswerAnalysis(BaseModel):
    """Complete grouped answer analysis structure."""
    query: str
    sub_questions: List[SubQuestionAnalysis] = Field(default_factory=list)
    references: List[Dict[str, Any]] = Field(default_factory=list)
    final_summary: Optional[str] = None
    generated_at: Optional[str] = None

    class Config:
        extra = 'allow'


class ValidatedQueryResponse(BaseModel):
    """Validated response for API output."""
    execution_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    mode: str = Field(pattern="^(dynamic|cached)$")
    status: str = Field(pattern="^(success|error)$")
    
    planning: PlanningInfo
    grouped_answer: str = Field(min_length=1)
    chunks_used: int = Field(ge=0)
    papers_found: List[PaperInfo] = Field(default_factory=list)
    
    verification: VerificationResult
    
    summary: Optional[str] = None
    
    total_time_ms: float = Field(ge=0)
    warnings: List[str] = Field(default_factory=list)

    class Config:
        extra = 'allow'


def validate_llm_output(data: Dict[str, Any]) -> ValidatedQueryResponse:
    """
    Validate LLM output with Pydantic.
    
    Raises ValidationError if the output doesn't conform to expected structure.
    """
    return ValidatedQueryResponse.model_validate(data)


def validate_grouped_answer(data: Dict[str, Any]) -> GroupedAnswerAnalysis:
    """Validate grouped answer analysis structure."""
    return GroupedAnswerAnalysis.model_validate(data)
