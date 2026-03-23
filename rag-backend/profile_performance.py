"""Performance profiling for Blues XAI backend."""

import time
import json
from typing import Dict, List, Any
from statistics import mean, stdev, median

from src.generation.inference_engine import InferenceEngine
from src.generation.refined_generator import RefinedAnswerGenerator
from src.generation.integration import InferenceAndGenerationPipeline
from src.llm.factory import get_llm


# Test Data
TEST_CHUNKS_20 = [
    {
        "chunk_id": f"chunk_{i}",
        "text": """This study investigates the effectiveness of transformer-based architectures in NLP tasks.
        We employed BERT and GPT models for our experiments. Our methodology assumes that
        pre-trained embeddings provide significant advantages. We validated our approach using
        the GLUE benchmark, constrained by limited computational resources. Results show that
        BERT achieves 88.5% accuracy on STS-B and 91.2% on MNLI tasks.""",
        "paper_title": f"Study on Transformers Part {i}",
        "paper_year": 2023 + (i % 2),
        "paper_id": f"paper_{i}",
        "section": "methodology" if i % 3 == 0 else "results",
        "similarity_score": 0.75 + (i * 0.01),
    }
    for i in range(20)
]

TEST_CHUNKS_50 = TEST_CHUNKS_20 + [
    {
        "chunk_id": f"chunk_{i}",
        "text": "Additional research on neural architectures and their applications.",
        "paper_title": f"Extended Study {i}",
        "paper_year": 2024,
        "paper_id": f"paper_{i}",
        "section": "discussion",
        "similarity_score": 0.70 + (i * 0.005),
    }
    for i in range(20, 50)
]

TEST_QUERY = "What are the key findings about transformer architectures?"
TEST_SUB_QUESTIONS = [
    "How do BERT and GPT perform?",
    "What are the limitations?",
    "How does fine-tuning help?",
]


def profile_inference_engine(chunks: List[Dict[str, Any]], iterations: int = 3) -> Dict[str, float]:
    """Profile InferenceEngine (Target: <2s per 20-chunk batch)"""
    print(f"\n[PROFILE] InferenceEngine.infer_from_chunks()")
    print(f"   Chunks: {len(chunks)} | Iterations: {iterations}")
    print("   Target: <2.0 seconds")
    
    engine = InferenceEngine()
    times = []
    
    for i in range(iterations):
        start = time.perf_counter()
        result = engine.infer_from_chunks(chunks)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        
        print(f"   Run {i+1}: {elapsed*1000:.1f}ms (insights: {len(result['methodology_insights'])}, findings: {len(result['experimental_findings'])})")
    
    mean_time = mean(times)
    stats = {
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
        "mean_ms": mean_time * 1000,
        "median_ms": median(times) * 1000,
        "stdev_ms": stdev(times) * 1000 if len(times) > 1 else 0,
        "target_ms": 2000,
        "passed": mean_time < 2.0,
    }
    
    status = "PASS" if stats["passed"] else "FAIL"
    print(f"   [{status}] Mean: {stats['mean_ms']:.1f}ms (Target: 2000ms)")
    
    return stats


def profile_refined_generator(chunks: List[Dict[str, Any]], iterations: int = 2) -> Dict[str, float]:
    """Profile RefinedAnswerGenerator (Target: <5s)"""
    print(f"\n[PROFILE] RefinedAnswerGenerator.generate_refined_answer()")
    print(f"   Chunks: {len(chunks)} | Iterations: {iterations}")
    print("   Target: <5.0 seconds (includes LLM)")
    
    try:
        llm = get_llm()
        generator = RefinedAnswerGenerator(llm)
        times = []
        
        for i in range(iterations):
            start = time.perf_counter()
            result = generator.generate_refined_answer(
                question=TEST_QUERY,
                sub_questions=TEST_SUB_QUESTIONS,
                chunks=chunks,
                verification_result=None
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            print(f"   Run {i+1}: {elapsed*1000:.1f}ms (confidence: {result['answer_confidence']:.2%})")
        
        mean_time = mean(times)
        stats = {
            "min_ms": min(times) * 1000,
            "max_ms": max(times) * 1000,
            "mean_ms": mean_time * 1000,
            "median_ms": median(times) * 1000,
            "stdev_ms": stdev(times) * 1000 if len(times) > 1 else 0,
            "target_ms": 5000,
            "passed": mean_time < 5.0,
        }
        
        status = "PASS" if stats["passed"] else "WARN"
        print(f"   [{status}] Mean: {stats['mean_ms']:.1f}ms (Target: 5000ms)")
        
        return stats
    
    except Exception as e:
        print(f"   [ERROR]: {e}")
        return {
            "min_ms": 0, "max_ms": 0, "mean_ms": 0, "median_ms": 0,
            "stdev_ms": 0, "target_ms": 5000, "passed": False, "error": str(e),
        }


def profile_integration_pipeline(chunks: List[Dict[str, Any]], iterations: int = 2) -> Dict[str, float]:
    """Profile full pipeline (Target: <7s)"""
    print(f"\n[PROFILE] InferenceAndGenerationPipeline")
    print(f"   Chunks: {len(chunks)} | Iterations: {iterations}")
    print("   Target: <7.0 seconds")
    
    try:
        llm = get_llm()
        pipeline = InferenceAndGenerationPipeline(llm)
        times = []
        
        for i in range(iterations):
            start = time.perf_counter()
            result = pipeline.process(
                main_query=TEST_QUERY,
                sub_questions=TEST_SUB_QUESTIONS,
                retrieved_chunks=chunks,
                verification_result=None,
                include_verification=False
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            inference_time = result['timing']['inference_extraction_ms']
            generation_time = result['timing']['answer_generation_ms']
            print(f"   Run {i+1}: {elapsed*1000:.1f}ms (inference: {inference_time:.1f}ms, gen: {generation_time:.1f}ms)")
        
        mean_time = mean(times)
        stats = {
            "min_ms": min(times) * 1000,
            "max_ms": max(times) * 1000,
            "mean_ms": mean_time * 1000,
            "median_ms": median(times) * 1000,
            "stdev_ms": stdev(times) * 1000 if len(times) > 1 else 0,
            "target_ms": 7000,
            "passed": mean_time < 7.0,
        }
        
        status = "PASS" if stats["passed"] else "WARN"
        print(f"   [{status}] Mean: {stats['mean_ms']:.1f}ms (Target: 7000ms)")
        
        return stats
    
    except Exception as e:
        print(f"   [ERROR]: {e}")
        return {
            "min_ms": 0, "max_ms": 0, "mean_ms": 0, "median_ms": 0,
            "stdev_ms": 0, "target_ms": 7000, "passed": False, "error": str(e),
        }


def profile_chunk_sensitivity() -> Dict[str, Any]:
    """Test performance across different chunk counts"""
    print(f"\n[ANALYSIS] Chunk Size Sensitivity")
    
    chunk_counts = [10, 20, 50]
    results = {}
    
    for count in chunk_counts:
        chunks = TEST_CHUNKS_50[:count]
        print(f"\n   Testing with {count} chunks...")
        
        engine = InferenceEngine()
        start = time.perf_counter()
        result = engine.infer_from_chunks(chunks)
        elapsed = (time.perf_counter() - start) * 1000
        
        results[f"{count}_chunks"] = {
            "time_ms": elapsed,
            "insights": len(result['methodology_insights']),
            "findings": len(result['experimental_findings']),
        }
        
        print(f"      Time: {elapsed:.1f}ms | Insights: {len(result['methodology_insights'])} | Findings: {len(result['experimental_findings'])}")
    
    return results


def run_performance_profile():
    """Run all performance profiling tests"""
    
    print("\n" + "=" * 80)
    print("[PROFILING] BLUES XAI PERFORMANCE ANALYSIS")
    print("=" * 80)
    print("\nTest Configuration:")
    print("  - Small batch: 20 chunks (standard retrieval)")
    print("  - Large batch: 50 chunks (dynamic retrieval)")
    print(f"  - Query: '{TEST_QUERY}'")
    
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "components": {}
    }
    
    # Profile with 20 chunks
    results["components"]["inference_engine_20"] = profile_inference_engine(TEST_CHUNKS_20, iterations=3)
    results["components"]["refined_generator_20"] = profile_refined_generator(TEST_CHUNKS_20, iterations=2)
    results["components"]["pipeline_20"] = profile_integration_pipeline(TEST_CHUNKS_20, iterations=2)
    
    # Profile with 50 chunks
    print("\n" + "-" * 80)
    print("[TEST] 50-Chunk Batch (Dynamic Retrieval)")
    print("-" * 80)
    results["components"]["inference_engine_50"] = profile_inference_engine(TEST_CHUNKS_50, iterations=2)
    
    # Chunk sensitivity
    results["chunk_sensitivity"] = profile_chunk_sensitivity()
    
    # Summary
    print("\n" + "=" * 80)
    print("[SUMMARY] PERFORMANCE TEST RESULTS")
    print("=" * 80)
    
    passed = sum(1 for r in results["components"].values() if r.get("passed", False))
    total = len(results["components"])
    
    print(f"\nTests Passed: {passed}/{total}")
    
    for name, stats in results["components"].items():
        mean_time = stats.get("mean_ms", 0)
        target = stats.get("target_ms", 0)
        ratio = mean_time / target if target > 0 else 0
        status = "OK" if stats.get("passed", False) else "FAIL"
        print(f"  [{status}] {name:30} {mean_time:7.1f}ms / {target:7.1f}ms ({ratio:5.1%})")
    
    # Save results
    output_file = "output/performance_profile.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")
    
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    results = run_performance_profile()
