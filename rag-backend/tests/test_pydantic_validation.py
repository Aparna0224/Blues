"""Unit tests for Pydantic validation schemas."""

import pytest
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.validation.schemas import (
    EvidenceUnit,
    PaperEvidence,
    ConflictAnalysis,
    SubQuestionAnalysis,
    PlanningInfo,
    VerificationResult,
    PaperInfo,
    GroupedAnswerAnalysis,
    ValidatedQueryResponse,
    validate_llm_output,
    validate_grouped_answer,
)


class TestEvidenceUnit:
    """Tests for EvidenceUnit schema."""

    def test_valid_evidence_unit(self):
        evidence = EvidenceUnit(
            chunk_id="c1",
            section="introduction",
            location_start=0,
            location_end=100,
            relevance=0.85,
            confidence=0.9,
            confidence_band="high",
            text="This is valid evidence text.",
        )
        assert evidence.chunk_id == "c1"
        assert evidence.relevance == 0.85
        assert evidence.confidence == 0.9

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            EvidenceUnit(
                chunk_id="c1",
                section="intro",
                location_start=0,
                location_end=100,
                relevance=1.5,  # Should be 0-1
                confidence=0.9,
                confidence_band="high",
                text="Evidence",
            )
        assert "relevance" in str(exc_info.value)

    def test_confidence_out_of_range_low_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            EvidenceUnit(
                chunk_id="c1",
                section="intro",
                location_start=0,
                location_end=100,
                relevance=-0.1,
                confidence=0.9,
                confidence_band="high",
                text="Evidence",
            )
        assert "relevance" in str(exc_info.value)

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            EvidenceUnit(
                chunk_id="c1",
                section="intro",
                location_start=0,
                location_end=100,
                relevance=0.5,
                confidence=0.9,
                confidence_band="medium",
                text="   ",  # Whitespace only
            )
        assert "empty" in str(exc_info.value).lower()

    def test_text_stripped(self):
        evidence = EvidenceUnit(
            chunk_id="c1",
            section="intro",
            location_start=0,
            location_end=100,
            relevance=0.5,
            confidence=0.9,
            confidence_band="medium",
            text="  Trimmed text  ",
        )
        assert evidence.text == "Trimmed text"

    def test_optional_fields(self):
        evidence = EvidenceUnit(
            chunk_id="c1",
            section="intro",
            location_start=0,
            location_end=100,
            relevance=0.5,
            confidence=0.9,
            confidence_band="medium",
            text="Evidence",
        )
        assert evidence.paper_id is None
        assert evidence.subquery_similarity == 0.0


class TestPaperEvidence:
    """Tests for PaperEvidence schema."""

    def test_valid_paper_evidence(self):
        evidence = PaperEvidence(
            paper_id="p1",
            paper_title="Test Paper",
            evidence_units=[
                EvidenceUnit(
                    chunk_id="c1",
                    section="intro",
                    location_start=0,
                    location_end=100,
                    relevance=0.8,
                    confidence=0.9,
                    confidence_band="high",
                    text="First evidence.",
                ),
                EvidenceUnit(
                    chunk_id="c2",
                    section="methods",
                    location_start=100,
                    location_end=200,
                    relevance=0.7,
                    confidence=0.85,
                    confidence_band="medium",
                    text="Second evidence.",
                ),
            ],
        )
        assert evidence.paper_id == "p1"
        assert len(evidence.evidence_units) == 2

    def test_empty_evidence_units_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            PaperEvidence(
                paper_id="p1",
                paper_title="Test Paper",
                evidence_units=[],  # Must have at least one
            )
        assert "at least one" in str(exc_info.value).lower()

    def test_optional_metadata(self):
        evidence = PaperEvidence(
            paper_id="p1",
            paper_title="Test Paper",
            paper_year="2024",
            doi="10.1234/test",
            link="https://example.com/paper",
            evidence_units=[
                EvidenceUnit(
                    chunk_id="c1",
                    section="intro",
                    location_start=0,
                    location_end=100,
                    relevance=0.8,
                    confidence=0.9,
                    confidence_band="high",
                    text="Evidence.",
                ),
            ],
        )
        assert evidence.paper_year == "2024"
        assert evidence.doi == "10.1234/test"


class TestConflictAnalysis:
    """Tests for ConflictAnalysis schema."""

    def test_valid_conflict(self):
        conflict = ConflictAnalysis(
            claim_a="RAG improves accuracy",
            claim_b="RAG has no effect",
            type="contradiction",
            strength=0.9,
            explanation="Studies show mixed results.",
        )
        assert conflict.type == "contradiction"
        assert conflict.strength == 0.9

    def test_strength_out_of_range_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ConflictAnalysis(
                claim_a="Claim A",
                claim_b="Claim B",
                type="contradiction",
                strength=1.5,  # Should be 0-1
                explanation="Explanation",
            )
        assert "strength" in str(exc_info.value)


class TestSubQuestionAnalysis:
    """Tests for SubQuestionAnalysis schema."""

    def test_valid_subquestion_analysis(self):
        analysis = SubQuestionAnalysis(
            question="How does RAG work?",
            intent="methodology",
            papers=[],
            conflicts=[],
        )
        assert analysis.question == "How does RAG work?"
        assert analysis.intent == "methodology"

    def test_empty_string_question_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            SubQuestionAnalysis(
                question="",  # Empty string
                papers=[],
                conflicts=[],
            )
        assert "string_too_short" in str(exc_info.value)


class TestPlanningInfo:
    """Tests for PlanningInfo schema."""

    def test_valid_planning_info(self):
        planning = PlanningInfo(
            main_question="What is RAG?",
            sub_questions=["How does RAG work?", "Why use RAG?"],
            search_queries=["RAG retrieval augmented generation", "RAG methodology"],
        )
        assert len(planning.sub_questions) == 2
        assert len(planning.search_queries) == 2

    def test_empty_main_question_raises(self):
        with pytest.raises(ValidationError):
            PlanningInfo(
                main_question="",  # Required min_length=1
                sub_questions=[],
                search_queries=[],
            )


class TestVerificationResult:
    """Tests for VerificationResult schema."""

    def test_valid_verification_result(self):
        result = VerificationResult(
            confidence_score=0.85,
            confidence_band="high",
            papers_verified=5,
            claims_verified=10,
            claims_supported=8,
            claims_contradicted=1,
            evidence_sources=["paper1", "paper2"],
        )
        assert result.confidence_score == 0.85
        assert result.papers_verified == 5

    def test_negative_verified_count_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            VerificationResult(
                papers_verified=-1,  # Must be >= 0
            )
        assert "papers_verified" in str(exc_info.value)

    def test_optional_fields_default(self):
        result = VerificationResult()
        assert result.confidence_score is None
        assert result.papers_verified == 0
        assert result.claims_verified == 0


class TestPaperInfo:
    """Tests for PaperInfo schema."""

    def test_valid_paper_info(self):
        paper = PaperInfo(
            paper_id="p1",
            title="RAG Study 2024",
            authors="John Doe, Jane Smith",
            year=2024,
            doi="10.1234/example",
            source="semantic_scholar",
        )
        assert paper.title == "RAG Study 2024"
        assert paper.year == 2024

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            PaperInfo(
                paper_id="p1",
                title="",  # Required min_length=1
            )


class TestValidatedQueryResponse:
    """Tests for ValidatedQueryResponse schema."""

    def test_valid_response(self):
        response = ValidatedQueryResponse(
            execution_id="exec-123",
            query="What is RAG?",
            mode="dynamic",
            status="success",
            planning=PlanningInfo(
                main_question="What is RAG?",
                sub_questions=["How does RAG work?"],
                search_queries=["RAG definition"],
            ),
            grouped_answer="RAG combines retrieval with generation.",
            chunks_used=10,
            verification=VerificationResult(
                confidence_score=0.8,
            ),
            total_time_ms=1500.0,
        )
        assert response.execution_id == "exec-123"
        assert response.status == "success"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ValidatedQueryResponse(
                execution_id="exec-123",
                query="What is RAG?",
                mode="invalid_mode",  # Must be "dynamic" or "cached"
                status="success",
                planning=PlanningInfo(main_question="RAG?"),
                grouped_answer="Answer",
                chunks_used=5,
                verification=VerificationResult(),
                total_time_ms=1000.0,
            )
        assert "pattern" in str(exc_info.value)

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ValidatedQueryResponse(
                execution_id="exec-123",
                query="What is RAG?",
                mode="dynamic",
                status="invalid_status",  # Must be "success" or "error"
                planning=PlanningInfo(main_question="RAG?"),
                grouped_answer="Answer",
                chunks_used=5,
                verification=VerificationResult(),
                total_time_ms=1000.0,
            )
        assert "pattern" in str(exc_info.value)

    def test_negative_chunks_used_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ValidatedQueryResponse(
                execution_id="exec-123",
                query="What is RAG?",
                mode="dynamic",
                status="success",
                planning=PlanningInfo(main_question="RAG?"),
                grouped_answer="Answer",
                chunks_used=-1,  # Must be >= 0
                verification=VerificationResult(),
                total_time_ms=1000.0,
            )
        assert "chunks_used" in str(exc_info.value)

    def test_extra_fields_allowed(self):
        response = ValidatedQueryResponse(
            execution_id="exec-123",
            query="What is RAG?",
            mode="dynamic",
            status="success",
            planning=PlanningInfo(main_question="RAG?"),
            grouped_answer="Answer",
            chunks_used=5,
            verification=VerificationResult(),
            total_time_ms=1000.0,
            custom_field="This is allowed",  # extra='allow'
        )
        assert response.custom_field == "This is allowed"


class TestValidateFunctions:
    """Tests for validation utility functions."""

    def test_validate_llm_output_valid(self):
        data = {
            "execution_id": "exec-1",
            "query": "Test query",
            "mode": "dynamic",
            "status": "success",
            "planning": {
                "main_question": "Test?",
                "sub_questions": [],
                "search_queries": [],
            },
            "grouped_answer": "Answer text",
            "chunks_used": 5,
            "verification": {},
            "total_time_ms": 1000.0,
        }
        result = validate_llm_output(data)
        assert isinstance(result, ValidatedQueryResponse)

    def test_validate_llm_output_invalid_raises(self):
        data = {
            "execution_id": "",  # Invalid - min_length=1
            "query": "Test",
            "mode": "invalid",
            "status": "invalid",
            "planning": {"main_question": ""},
            "grouped_answer": "",
            "chunks_used": -1,
            "verification": {},
            "total_time_ms": -100.0,
        }
        with pytest.raises(ValidationError):
            validate_llm_output(data)

    def test_validate_grouped_answer_valid(self):
        data = {
            "query": "What is RAG?",
            "sub_questions": [
                {
                    "question": "How does RAG work?",
                    "papers": [],
                    "conflicts": [],
                }
            ],
            "references": [],
        }
        result = validate_grouped_answer(data)
        assert isinstance(result, GroupedAnswerAnalysis)
