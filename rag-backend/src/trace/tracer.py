"""Execution Tracer — deterministic, reproducible pipeline trace (Stage 5).

Captures every decision in the Agentic RAG pipeline so that:
  - The full execution can be reconstructed from the trace alone
  - Confidence scores are reproducible from stored metrics
  - Failures are recorded without discarding partial data
  - Traces are fully JSON-serializable and storable in MongoDB

Trace version: 1.0
"""

import uuid
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import Config


# Maximum length for raw LLM output stored in trace (chars).
_MAX_LLM_OUTPUT_LEN = 4_000


def _truncate(text: str, max_len: int = _MAX_LLM_OUTPUT_LEN) -> str:
    """Truncate long text to keep trace under size policy."""
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len] + f"... [truncated, total {len(text)} chars]"


class ExecutionTracer:
    """Records a full pipeline execution trace.

    Usage::

        tracer = ExecutionTracer(query="...", mode="dynamic")
        tracer.record_planning(...)
        tracer.record_retrieval(...)
        tracer.record_filtering(...)
        tracer.record_evidence_selection(...)
        tracer.record_verification(...)
        trace = tracer.finalize()   # → dict, JSON-serializable

    If any stage throws, call ``record_error()`` and the tracer
    preserves all stages that completed successfully.
    """

    TRACE_VERSION = "1.0"

    # ─────────────────────────────────────────────────────────────
    # Construction
    # ─────────────────────────────────────────────────────────────

    def __init__(self, query: str, mode: str = "dynamic") -> None:
        self._execution_id = str(uuid.uuid4())
        self._timestamp = datetime.now(timezone.utc).isoformat()
        self._start_time = time.perf_counter()

        # Stage timers (seconds)
        self._stage_start: float = 0.0
        self._timings: Dict[str, float] = {}

        # Top-level fields
        self._query = query
        self._mode = mode
        self._status = "success"  # may become "partial" or "failed"

        # Config snapshot
        self._config = self._capture_config()

        # Stage data (populated lazily)
        self._planning: Optional[Dict[str, Any]] = None
        self._retrieval: Optional[Dict[str, Any]] = None
        self._filtering: Optional[Dict[str, Any]] = None
        self._evidence_selection: Optional[Dict[str, Any]] = None
        self._verification: Optional[Dict[str, Any]] = None
        self._confidence_score: Optional[float] = None

        # Errors
        self._errors: List[Dict[str, str]] = []

    # ─────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────

    @property
    def execution_id(self) -> str:
        return self._execution_id

    # ─────────────────────────────────────────────────────────────
    # Timer helpers
    # ─────────────────────────────────────────────────────────────

    def _start_stage(self) -> None:
        self._stage_start = time.perf_counter()

    def _end_stage(self, stage_name: str) -> float:
        elapsed_ms = round((time.perf_counter() - self._stage_start) * 1000, 1)
        self._timings[f"{stage_name}_ms"] = elapsed_ms
        return elapsed_ms

    # ─────────────────────────────────────────────────────────────
    # Config snapshot
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _capture_config() -> Dict[str, Any]:
        """Snapshot of all determinism-relevant configuration."""
        provider = Config.LLM_PROVIDER
        if provider == "local":
            llm_model = Config.OLLAMA_MODEL
        elif provider == "gemini":
            llm_model = Config.GEMINI_MODEL
        elif provider == "groq":
            llm_model = Config.GROQ_MODEL
        else:
            llm_model = "unknown"

        return {
            "embedding_model": Config.EMBEDDING_MODEL,
            "embedding_dimension": Config.EMBEDDING_DIMENSION,
            "vector_index_type": "FAISS IndexFlatIP",
            "similarity_threshold": 0.70,
            "diversity_cap": 5,
            "confidence_formula": "0.5*S + 0.3*D + 0.2*E",
            "density_formula": "claims_used / total_chunks_retrieved",
            "llm_provider": provider,
            "llm_model": llm_model,
            "temperature": Config.LLM_TEMPERATURE,
            "top_k": Config.TOP_K,
            "min_chunk_sentences": Config.MIN_CHUNK_SENTENCES,
            "max_chunk_sentences": Config.MAX_CHUNK_SENTENCES,
        }

    # ─────────────────────────────────────────────────────────────
    # Stage recorders
    # ─────────────────────────────────────────────────────────────

    def record_planning(
        self,
        input_question: str,
        sub_questions: List[str],
        search_queries: List[str],
        llm_raw_output: str = "",
        latency_ms: Optional[float] = None,
    ) -> None:
        """Record the planning / query-decomposition stage."""
        self._planning = {
            "input_question": input_question,
            "sub_questions": list(sub_questions),
            "search_queries": list(search_queries),
            "llm_raw_output": _truncate(llm_raw_output),
            "llm_latency_ms": latency_ms,
        }

    def record_retrieval(
        self,
        per_query: Optional[List[Dict[str, Any]]] = None,
        total_chunks_before_merge: int = 0,
        unique_chunks_after_merge: int = 0,
    ) -> None:
        """Record the retrieval stage."""
        # Sanitise per_query entries to be JSON-safe
        safe_per_query = []
        for pq in (per_query or []):
            safe_per_query.append({
                "search_query": pq.get("search_query", ""),
                "top_k": pq.get("top_k", 0),
                "retrieved_chunk_ids": list(pq.get("retrieved_chunk_ids", [])),
                "similarity_scores": [
                    round(float(s), 4)
                    for s in pq.get("similarity_scores", [])
                ],
                "ordered_by": "similarity_desc",
            })

        self._retrieval = {
            "per_query": safe_per_query,
            "total_chunks_before_merge": total_chunks_before_merge,
            "unique_chunks_after_merge": unique_chunks_after_merge,
            "ordering_rule": "stable_sort_similarity_then_chunk_id",
        }

    def record_filtering(
        self,
        total_claims_received: int = 0,
        after_deduplication: int = 0,
        after_relevance_filter: int = 0,
        above_similarity_threshold: int = 0,
        claims_rejected: int = 0,
        rejected_claim_ids: Optional[List[str]] = None,
    ) -> None:
        """Record the claim-filtering stage (from VerificationAgent audit)."""
        self._filtering = {
            "total_claims_received": total_claims_received,
            "after_deduplication": after_deduplication,
            "after_relevance_filter": after_relevance_filter,
            "above_similarity_threshold": above_similarity_threshold,
            "claims_rejected": claims_rejected,
            "rejected_claim_ids": list(rejected_claim_ids or []),
        }

    def record_evidence_selection(
        self,
        claims_used: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Record evidence-selection (which sentences were kept)."""
        safe_claims: List[Dict[str, Any]] = []
        for c in (claims_used or []):
            safe_claims.append({
                "chunk_id": c.get("chunk_id", c.get("paper_id", "")),
                "selected_sentence": _truncate(
                    c.get("claim", c.get("evidence_sentence", "")), 500
                ),
                "similarity_score": round(float(c.get("similarity_score", 0)), 4),
                "paper_id": c.get("paper_id", ""),
                "sub_question": c.get("sub_question", ""),
            })

        self._evidence_selection = {
            "claims_used": safe_claims,
            "selection_rule": "max_sentence_similarity",
        }

    def record_verification(
        self,
        verification_result: Dict[str, Any],
    ) -> None:
        """Record the verification stage from VerificationAgent output."""
        metrics = verification_result.get("metrics", {})

        self._verification = {
            "metrics": {
                "avg_similarity": metrics.get("avg_similarity", 0.0),
                "source_diversity": metrics.get("source_diversity", 0),
                "normalized_source_diversity": metrics.get(
                    "normalized_source_diversity", 0.0
                ),
                "evidence_density": metrics.get("evidence_density", 0.0),
                "conflicts_detected": metrics.get("conflicts_detected", False),
            },
            "confidence_formula": "0.5*S + 0.3*D + 0.2*E",
            "confidence_score": verification_result.get("confidence_score"),
            "penalties_applied": [],
            "warnings": list(verification_result.get("warnings", [])),
        }

        # Populate penalties from warnings (reverse-engineer)
        warnings = verification_result.get("warnings", [])
        if "Low source diversity" in warnings:
            self._verification["penalties_applied"].append(
                "single_source_penalty: -0.10"
            )
        if "Mixed findings across sources" in warnings:
            self._verification["penalties_applied"].append(
                "conflict_penalty: -0.15"
            )
        if "Weak evidence strength" in warnings or \
           "All evidence weakly related" in warnings:
            self._verification["penalties_applied"].append(
                "weak_similarity_multiplier: ×0.70"
            )

        self._confidence_score = verification_result.get("confidence_score")

    # ─────────────────────────────────────────────────────────────
    # Error / failure protocol
    # ─────────────────────────────────────────────────────────────

    def record_error(
        self, stage: str, error: Exception
    ) -> None:
        """Record a stage failure.  Preserves partial trace."""
        self._errors.append({
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error)[:1000],
        })
        # Downgrade status — never upgrade back
        if self._status == "success":
            self._status = "partial"

    def mark_failed(self) -> None:
        """Mark entire execution as failed (unrecoverable)."""
        self._status = "failed"
        self._confidence_score = None

    # ─────────────────────────────────────────────────────────────
    # Finalize → full trace dict
    # ─────────────────────────────────────────────────────────────

    def finalize(self) -> Dict[str, Any]:
        """Build the complete trace object.

        Returns a dict that is:
          - Fully JSON-serializable
          - Contains no binary blobs or circular references
          - ≤ 5 MB in practice (LLM outputs are truncated)
        """
        total_ms = round((time.perf_counter() - self._start_time) * 1000, 1)
        self._timings["total_execution_ms"] = total_ms

        trace: Dict[str, Any] = {
            "trace_version": self.TRACE_VERSION,
            "execution_id": self._execution_id,
            "timestamp": self._timestamp,
            "status": self._status,
            "query": {
                "original_text": self._query,
                "mode": self._mode,
            },
            "config": self._config,
            "stages": {
                "planning": self._planning,
                "retrieval": self._retrieval,
                "filtering": self._filtering,
                "evidence_selection": self._evidence_selection,
                "verification": self._verification,
            },
            "final_output": {
                "confidence_score": self._confidence_score,
            },
            "timing": self._timings,
            "errors": self._errors,
        }

        return trace

    # ─────────────────────────────────────────────────────────────
    # Convenience: save to file
    # ─────────────────────────────────────────────────────────────

    def save_trace(self, directory: str = "output") -> str:
        """Finalize and write trace JSON to *directory*.

        Returns the path of the written file.
        """
        import os

        trace = self.finalize()
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"trace_{self._execution_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, ensure_ascii=False, default=str)
        return path
