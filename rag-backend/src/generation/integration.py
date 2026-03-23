"""
Integration layer for InferenceEngine and RefinedAnswerGenerator.

Provides a clean interface to insert inference and answer generation
stages into the query pipeline after retrieval.
"""

import time
from typing import List, Dict, Any, Optional
from src.generation.inference_engine import InferenceEngine
from src.generation.refined_generator import RefinedAnswerGenerator


class InferenceAndGenerationPipeline:
    """
    Unified pipeline for inference extraction and refined answer generation.
    
    Flow:
    1. Extract inferences from retrieved chunks (InferenceEngine)
    2. Generate refined 5-section answer (RefinedAnswerGenerator)
    3. Return enriched result with confidence and structure
    """
    
    def __init__(self, llm=None):
        """
        Initialize pipeline.
        
        Args:
            llm: LLM instance (optional, used by RefinedAnswerGenerator)
        """
        self.inference_engine = InferenceEngine()
        self.refined_generator = RefinedAnswerGenerator(llm) if llm else None
        self.llm = llm
    
    def process(
        self,
        main_query: str,
        sub_questions: List[str],
        retrieved_chunks: List[Dict[str, Any]],
        verification_result: Optional[Dict[str, Any]] = None,
        include_verification: bool = False
    ) -> Dict[str, Any]:
        """
        Process retrieved chunks through inference and answer generation.
        
        Args:
            main_query: The main user question
            sub_questions: Decomposed sub-questions from planner
            retrieved_chunks: Chunks retrieved by retriever
            verification_result: Optional verification results (from VerificationAgent)
            include_verification: Whether to include verification in answer generation
            
        Returns:
            Dictionary with:
            - answer: Refined 5-section answer
            - answer_structure: "5-section" format indicator
            - answer_confidence: 0.0-1.0 confidence score
            - inference_summary: Details about extracted inferences
            - methodology_insights: Extracted methodology details
            - experimental_findings: Extracted experimental details
            - inference_chains: Built inference chains with confidence
            - synthesis: Synthesized narrative
            - inferences_confidence: Overall inference confidence
            - timing: Execution timing breakdown
        """
        timing = {}
        
        # Step 1: Extract inferences
        t0 = time.perf_counter()
        inferences = self.inference_engine.infer_from_chunks(retrieved_chunks)
        timing["inference_extraction_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        
        # Step 2: Generate refined answer
        t0 = time.perf_counter()
        answer_result = self.refined_generator.generate_refined_answer(
            question=main_query,
            sub_questions=sub_questions,
            chunks=retrieved_chunks,
            verification_result=verification_result if include_verification else None
        ) if self.refined_generator else {
            "answer": "Answer generation unavailable (no LLM configured)",
            "confidence": 0.0,
            "evidence_summary": "",
            "chunks_used": len(retrieved_chunks)
        }
        timing["answer_generation_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        
        # Build result
        result = {
            # Answer content
            "answer": answer_result.get("answer", ""),
            "answer_structure": "5-section",
            "answer_confidence": answer_result.get("confidence", 0.0),
            
            # Inference details
            "inference_summary": {
                "methodology_insights_count": len(inferences.get("methodology_insights", [])),
                "experimental_findings_count": len(inferences.get("experimental_findings", [])),
                "inference_chains_count": len(inferences.get("inference_chains", [])),
                "overall_confidence": inferences.get("confidence", 0.0),
            },
            
            # Raw inference data
            "methodology_insights": inferences.get("methodology_insights", []),
            "experimental_findings": inferences.get("experimental_findings", []),
            "inference_chains": inferences.get("inference_chains", []),
            "synthesis": inferences.get("synthesis", ""),
            "inferences_confidence": inferences.get("confidence", 0.0),
            
            # Metadata
            "chunks_used": answer_result.get("chunks_used", len(retrieved_chunks)),
            "evidence_quality": answer_result.get("evidence_quality", "UNKNOWN"),
            "sources_count": answer_result.get("sources_count", 0),
            
            # Timing
            "timing": timing,
            "total_inference_ms": timing["inference_extraction_ms"] + timing["answer_generation_ms"],
        }
        
        return result


def integrate_inference_stage(
    query: str,
    sub_questions: List[str],
    retrieved_chunks: List[Dict[str, Any]],
    llm=None,
    verification_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to run inference + generation on retrieved chunks.
    
    Args:
        query: Main question
        sub_questions: Decomposed sub-questions
        retrieved_chunks: Retrieved chunks
        llm: LLM instance (optional)
        verification_result: Optional verification results
        
    Returns:
        Integrated inference and answer generation results
    """
    pipeline = InferenceAndGenerationPipeline(llm)
    return pipeline.process(
        main_query=query,
        sub_questions=sub_questions,
        retrieved_chunks=retrieved_chunks,
        verification_result=verification_result,
        include_verification=verification_result is not None
    )
