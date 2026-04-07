"""Canonical analysis_data schema and validator.

Defines the contract that every pipeline stage writes to and reads from.
Call ``validate_analysis_data`` at the start of the summarizer so missing
keys are logged immediately rather than silently producing blank output.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical schema  (type hints are for documentation — validation is soft)
# ---------------------------------------------------------------------------

ANALYSIS_DATA_SCHEMA: Dict[str, Any] = {
    "query": str,
    "sub_questions": [
        {
            "question": str,
            "intent": str,  # "dataset" | "methodology" | "results" | "general"
            "papers": [
                {
                    "paper_id": str,
                    "paper_title": str,
                    "evidence_units": [
                        {
                            "claim": str,
                            "text": str,
                            "section": str,
                            "score": float,
                        }
                    ],
                }
            ],
        }
    ],
    "references": [
        {
            "paper_id": str,
            "title": str,
            "year": str,
            "doi": str,
        }
    ],
    # NEW — Phase 3
    "paper_comparison_matrix": [
        {
            "paper_id": str,
            "title": str,
            "year": str,
            "datasets": [str],
            "model_names": [str],
            "method_keywords": [str],
            "metrics": [str],
            "sections_covered": [str],
            "top_evidence": str,
            "similarity_score": float,
        }
    ],
    # NEW — Phase 3
    "cross_paper_dataset_overlap": {
        # dataset_name -> [paper_title, ...]
    },
    "conflicts": [
        {
            "type": str,
            "strength": str,
            "papers": [str],
            "claim": str,
        }
    ],
    "confidence_score": float,
    # NEW — Phase 1
    "comparison_axes": [str],
}

# Keys that MUST be present for the summarizer to produce useful output.
_REQUIRED_KEYS = [
    "query",
    "sub_questions",
    "references",
]

# Keys that SHOULD be present for comparison-aware summaries.
_COMPARISON_KEYS = [
    "paper_comparison_matrix",
    "cross_paper_dataset_overlap",
    "comparison_axes",
]


def validate_analysis_data(data: Dict[str, Any]) -> List[str]:
    """Validate *analysis_data* against the canonical schema.

    Returns a list of human-readable warning strings for every missing or
    malformed key.  An empty list means the data is fully conformant.

    This function is intentionally **soft** — it logs warnings rather than
    raising exceptions so the pipeline can degrade gracefully.
    """
    if not isinstance(data, dict):
        msg = "analysis_data is not a dict — all downstream stages will fail"
        logger.warning(msg)
        return [msg]

    warnings: List[str] = []

    # --- required keys ---
    for key in _REQUIRED_KEYS:
        if key not in data:
            warnings.append(f"Missing required key: '{key}'")
        elif key == "sub_questions" and not isinstance(data[key], list):
            warnings.append(f"'{key}' should be a list, got {type(data[key]).__name__}")
        elif key == "references" and not isinstance(data[key], list):
            warnings.append(f"'{key}' should be a list, got {type(data[key]).__name__}")

    # --- comparison keys (warn, don't block) ---
    for key in _COMPARISON_KEYS:
        if key not in data or data[key] is None:
            warnings.append(f"Missing comparison key: '{key}' — summary will lack structured comparison")

    # --- structural checks on comparison matrix ---
    matrix = data.get("paper_comparison_matrix")
    if isinstance(matrix, list):
        for i, entry in enumerate(matrix):
            if not isinstance(entry, dict):
                warnings.append(f"paper_comparison_matrix[{i}] is not a dict")
                continue
            for field in ("paper_id", "title", "datasets", "metrics"):
                if field not in entry:
                    warnings.append(
                        f"paper_comparison_matrix[{i}] missing '{field}'"
                    )

    # --- confidence score ---
    if "confidence_score" in data:
        score = data["confidence_score"]
        if not isinstance(score, (int, float)):
            warnings.append(f"'confidence_score' should be numeric, got {type(score).__name__}")

    # Log all warnings
    for w in warnings:
        logger.warning("analysis_data validation: %s", w)

    return warnings
