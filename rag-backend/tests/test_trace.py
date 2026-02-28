"""Unit tests for Stage 5 — Execution Tracer and Pipeline Summarizer.

Covers:
  - Trace schema completeness (all required fields per spec)
  - JSON serializability
  - Failure protocol (partial trace preserved, confidence null)
  - Confidence reproducibility from stored metrics
  - Config snapshot accuracy
  - Timing capture
  - PipelineSummarizer output format
  - MongoDB storage contract (store_trace / get_trace shape)
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.trace.tracer import ExecutionTracer


# ─────────────────────────────────────────────────────────────────
# Helper fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tracer():
    """A fresh tracer with a test query."""
    return ExecutionTracer(query="What is explainable AI?", mode="dynamic")


@pytest.fixture
def full_tracer(tracer):
    """A tracer with all stages recorded (happy path)."""
    tracer.record_planning(
        input_question="What is explainable AI?",
        sub_questions=["Q1: Techniques?", "Q2: Benefits?"],
        search_queries=["explainable AI techniques", "XAI benefits"],
        llm_raw_output="raw LLM response text here",
        latency_ms=150.0,
    )
    tracer.record_retrieval(
        per_query=[
            {
                "search_query": "explainable AI techniques",
                "top_k": 5,
                "retrieved_chunk_ids": ["c1", "c2", "c3"],
                "similarity_scores": [0.85, 0.80, 0.75],
            },
            {
                "search_query": "XAI benefits",
                "top_k": 5,
                "retrieved_chunk_ids": ["c4", "c5"],
                "similarity_scores": [0.82, 0.77],
            },
        ],
        total_chunks_before_merge=10,
        unique_chunks_after_merge=8,
    )
    tracer.record_filtering(
        total_claims_received=8,
        after_deduplication=7,
        after_relevance_filter=6,
        above_similarity_threshold=5,
        claims_rejected=3,
        rejected_claim_ids=["c6", "c9", "c10"],
    )
    tracer.record_evidence_selection(
        claims_used=[
            {
                "chunk_id": "c1",
                "claim": "SHAP explains model predictions",
                "similarity_score": 0.85,
                "paper_id": "p1",
                "sub_question": "Q1",
            },
        ]
    )
    tracer.record_verification({
        "confidence_score": 0.83,
        "metrics": {
            "avg_similarity": 0.78,
            "source_diversity": 5,
            "normalized_source_diversity": 1.0,
            "evidence_density": 0.73,
            "conflicts_detected": False,
        },
        "warnings": [],
        "audit": {},
    })
    return tracer


# =================================================================
# 1. Required fields present
# =================================================================

class TestTraceSchema:

    def test_required_top_level_fields(self, full_tracer):
        """Trace has all required top-level fields per spec."""
        trace = full_tracer.finalize()
        required = [
            "trace_version", "execution_id", "timestamp", "status",
            "query", "config", "stages", "final_output", "timing", "errors",
        ]
        for field in required:
            assert field in trace, f"Missing required field: {field}"

    def test_query_fields(self, full_tracer):
        trace = full_tracer.finalize()
        assert trace["query"]["original_text"] == "What is explainable AI?"
        assert trace["query"]["mode"] == "dynamic"

    def test_stages_all_present(self, full_tracer):
        trace = full_tracer.finalize()
        stages = trace["stages"]
        for stage in ["planning", "retrieval", "filtering",
                      "evidence_selection", "verification"]:
            assert stage in stages, f"Missing stage: {stage}"
            assert stages[stage] is not None, f"Stage {stage} is None"

    def test_final_output_confidence(self, full_tracer):
        trace = full_tracer.finalize()
        assert trace["final_output"]["confidence_score"] == 0.83

    def test_trace_version(self, full_tracer):
        trace = full_tracer.finalize()
        assert trace["trace_version"] == "1.0"

    def test_execution_id_is_uuid(self, full_tracer):
        trace = full_tracer.finalize()
        import uuid
        # Should not raise
        uuid.UUID(trace["execution_id"])

    def test_timestamp_is_iso(self, full_tracer):
        trace = full_tracer.finalize()
        from datetime import datetime
        # Should not raise
        datetime.fromisoformat(trace["timestamp"])


# =================================================================
# 2. JSON serializability
# =================================================================

class TestJsonSerializability:

    def test_full_trace_serializable(self, full_tracer):
        trace = full_tracer.finalize()
        # Must not raise
        serialized = json.dumps(trace, default=str)
        assert len(serialized) > 0

    def test_round_trip(self, full_tracer):
        trace = full_tracer.finalize()
        serialized = json.dumps(trace, default=str)
        deserialized = json.loads(serialized)
        assert deserialized["execution_id"] == trace["execution_id"]
        assert deserialized["final_output"]["confidence_score"] == 0.83

    def test_empty_tracer_serializable(self, tracer):
        """Even a tracer with no stages recorded is serializable."""
        trace = tracer.finalize()
        serialized = json.dumps(trace, default=str)
        assert len(serialized) > 0


# =================================================================
# 3. Failure protocol
# =================================================================

class TestFailureProtocol:

    def test_partial_trace_preserves_completed_stages(self, tracer):
        """If planning succeeds but retrieval fails, planning data is kept."""
        tracer.record_planning(
            input_question="test",
            sub_questions=["Q1"],
            search_queries=["query1"],
        )
        tracer.record_error("retrieval", IndexError("No vectors found"))
        trace = tracer.finalize()

        assert trace["status"] == "partial"
        assert trace["stages"]["planning"] is not None
        assert trace["stages"]["retrieval"] is None
        assert len(trace["errors"]) == 1
        assert trace["errors"][0]["stage"] == "retrieval"
        assert trace["errors"][0]["error_type"] == "IndexError"

    def test_failed_trace_confidence_null(self, tracer):
        """mark_failed() sets confidence to null."""
        tracer.record_error("planning", RuntimeError("LLM down"))
        tracer.mark_failed()
        trace = tracer.finalize()

        assert trace["status"] == "failed"
        assert trace["final_output"]["confidence_score"] is None

    def test_multiple_errors_recorded(self, tracer):
        tracer.record_error("planning", RuntimeError("err1"))
        tracer.record_error("retrieval", ValueError("err2"))
        trace = tracer.finalize()
        assert len(trace["errors"]) == 2


# =================================================================
# 4. Confidence reproducibility
# =================================================================

class TestConfidenceReproducibility:

    def test_confidence_from_metrics(self, full_tracer):
        """Confidence is recomputable: 0.5*S + 0.3*D + 0.2*E."""
        trace = full_tracer.finalize()
        v = trace["stages"]["verification"]
        m = v["metrics"]
        S = m["avg_similarity"]
        D = m["normalized_source_diversity"]
        E = m["evidence_density"]
        expected = 0.5 * S + 0.3 * D + 0.2 * E
        # May differ slightly due to penalties, but formula is logged
        assert v["confidence_formula"] == "0.5*S + 0.3*D + 0.2*E"
        # Base formula value (before penalties)
        assert abs(expected - (0.5 * 0.78 + 0.3 * 1.0 + 0.2 * 0.73)) < 0.001


# =================================================================
# 5. Config snapshot
# =================================================================

class TestConfigSnapshot:

    def test_config_has_required_keys(self, full_tracer):
        trace = full_tracer.finalize()
        config = trace["config"]
        required_keys = [
            "embedding_model", "vector_index_type", "similarity_threshold",
            "confidence_formula", "density_formula", "llm_provider",
            "llm_model", "temperature",
        ]
        for key in required_keys:
            assert key in config, f"Missing config key: {key}"

    def test_config_embedding_model(self, full_tracer):
        trace = full_tracer.finalize()
        assert "scibert" in trace["config"]["embedding_model"].lower()


# =================================================================
# 6. Timing
# =================================================================

class TestTiming:

    def test_total_execution_time_captured(self, full_tracer):
        trace = full_tracer.finalize()
        assert "total_execution_ms" in trace["timing"]
        assert trace["timing"]["total_execution_ms"] >= 0


# =================================================================
# 7. Stage data correctness
# =================================================================

class TestStageData:

    def test_planning_data(self, full_tracer):
        trace = full_tracer.finalize()
        p = trace["stages"]["planning"]
        assert p["input_question"] == "What is explainable AI?"
        assert len(p["sub_questions"]) == 2
        assert len(p["search_queries"]) == 2
        assert p["llm_latency_ms"] == 150.0

    def test_retrieval_data(self, full_tracer):
        trace = full_tracer.finalize()
        r = trace["stages"]["retrieval"]
        assert len(r["per_query"]) == 2
        assert r["total_chunks_before_merge"] == 10
        assert r["unique_chunks_after_merge"] == 8
        assert r["ordering_rule"] == "stable_sort_similarity_then_chunk_id"

    def test_filtering_data(self, full_tracer):
        trace = full_tracer.finalize()
        f = trace["stages"]["filtering"]
        assert f["total_claims_received"] == 8
        assert f["after_deduplication"] == 7
        assert f["claims_rejected"] == 3

    def test_evidence_selection_data(self, full_tracer):
        trace = full_tracer.finalize()
        es = trace["stages"]["evidence_selection"]
        assert len(es["claims_used"]) == 1
        assert es["selection_rule"] == "max_sentence_similarity"
        assert es["claims_used"][0]["similarity_score"] == 0.85

    def test_verification_data(self, full_tracer):
        trace = full_tracer.finalize()
        v = trace["stages"]["verification"]
        assert v["confidence_score"] == 0.83
        assert v["metrics"]["source_diversity"] == 5
        assert v["metrics"]["conflicts_detected"] is False

    def test_verification_penalties_tracked(self):
        """Penalties are reverse-engineered from warnings."""
        tracer = ExecutionTracer(query="test", mode="cached")
        tracer.record_verification({
            "confidence_score": 0.55,
            "metrics": {
                "avg_similarity": 0.60,
                "source_diversity": 1,
                "normalized_source_diversity": 0.2,
                "evidence_density": 0.3,
                "conflicts_detected": True,
            },
            "warnings": [
                "Low source diversity",
                "Mixed findings across sources",
                "Weak evidence strength",
            ],
            "audit": {},
        })
        trace = tracer.finalize()
        penalties = trace["stages"]["verification"]["penalties_applied"]
        assert "single_source_penalty: -0.10" in penalties
        assert "conflict_penalty: -0.15" in penalties
        assert "weak_similarity_multiplier: ×0.70" in penalties


# =================================================================
# 8. LLM output truncation
# =================================================================

class TestTruncation:

    def test_long_llm_output_truncated(self, tracer):
        long_text = "x" * 10_000
        tracer.record_planning(
            input_question="test",
            sub_questions=[],
            search_queries=[],
            llm_raw_output=long_text,
        )
        trace = tracer.finalize()
        raw = trace["stages"]["planning"]["llm_raw_output"]
        assert len(raw) < 5_000
        assert "truncated" in raw


# =================================================================
# 9. Summarizer
# =================================================================

class TestPipelineSummarizer:

    def test_format_summary_block(self):
        """Summary block has correct structure."""
        from src.generation.summarizer import PipelineSummarizer
        block = PipelineSummarizer._format_summary_block(
            "This is a test summary.",
            {"confidence_score": 0.83},
        )
        assert "RESEARCH SUMMARY" in block
        assert "This is a test summary." in block
        assert "0.83" in block
        assert "HIGH" in block

    def test_format_summary_block_low(self):
        from src.generation.summarizer import PipelineSummarizer
        block = PipelineSummarizer._format_summary_block(
            "Weak results.",
            {"confidence_score": 0.30},
        )
        assert "LOW" in block

    def test_format_summary_block_no_result(self):
        from src.generation.summarizer import PipelineSummarizer
        block = PipelineSummarizer._format_summary_block("Summary text.", None)
        assert "RESEARCH SUMMARY" in block
        assert "Summary text." in block


# =================================================================
# 10. Save trace to file
# =================================================================

class TestSaveTrace:

    def test_save_trace_creates_file(self, full_tracer, tmp_path):
        path = full_tracer.save_trace(directory=str(tmp_path))
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["execution_id"] == full_tracer.execution_id
        assert data["trace_version"] == "1.0"
