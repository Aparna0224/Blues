"""LangGraph StateGraph orchestration for Agentic RAG.

Strict node separation with FULL production pipeline:
  plan → retrieve → rerank → generate → verify → [expand] → summarize

Key design decisions:
  - retrieve_node uses DynamicRetriever to fetch papers from APIs + web fallback
  - rerank_node applies global RRF fusion across all retrieved chunks
  - generate_node uses the full AnswerGenerator for rich evidence-mapped output
  - summarize_node uses PipelineSummarizer for structured narrative synthesis
"""
import json
import asyncio
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.orchestration.state import ResearchState

# Import Agents and Modules
from src.llm.factory import get_llm
from src.agents.planner import PlannerAgent
from src.agents.verifier import VerifierAgent
from src.retrieval.reranker import GlobalReranker
from src.evidence.extractor import EvidenceExtractor

# Lazy-loaded heavy modules (avoid circular imports at module level)
_llm = None
_planner = None
_verifier = None
_evidence_extractor = None

def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm

def _get_planner():
    global _planner
    if _planner is None:
        _planner = PlannerAgent(_get_llm())
    return _planner

def _get_verifier():
    global _verifier
    if _verifier is None:
        _verifier = VerifierAgent()
    return _verifier

def _get_evidence_extractor():
    global _evidence_extractor
    if _evidence_extractor is None:
        _evidence_extractor = EvidenceExtractor()
    return _evidence_extractor


# ---------------------------------------------------------
# Node Functions
# ---------------------------------------------------------

async def plan_node(state: ResearchState) -> ResearchState:
    """Decompose user query into sub-questions and search queries."""
    planner = _get_planner()
    plan = planner.plan(state["query"])
    return {
        "sub_queries": plan["sub_questions"],
        "search_queries": plan["search_queries"],
        "iteration_count": state.get("iteration_count", 0),
    }


async def retrieve_node(state: ResearchState) -> ResearchState:
    """Fetch papers from APIs (OpenAlex/Semantic Scholar) + existing BM25/FAISS,
    then return raw chunks for the reranker."""
    from src.retrieval.dynamic_retriever import DynamicRetriever
    from src.retrieval.hybrid_retriever import HybridRetrieverBase

    queries = state.get("search_queries", [])
    if not queries:
        queries = [state["query"]]

    all_chunks = []

    # --- Stage 1: Dynamic API retrieval (fetches NEW papers) ---
    paper_source = state.get("paper_source", "both")
    try:
        dynamic = DynamicRetriever(use_evidence=True, papers_per_query=5, source=paper_source)
        print(f"   Using paper source: {paper_source}")
        api_chunks = await dynamic.retrieve(
            search_queries=queries,
            main_query=state["query"],
            top_k=30,
            use_web_fallback=True,
        )
        all_chunks.extend(api_chunks)
        print(f"   ✓ DynamicRetriever returned {len(api_chunks)} chunks")
    except Exception as e:
        print(f"   ⚠ DynamicRetriever failed: {e}")

    # --- Stage 2: Existing BM25 retrieval (searches cached index) ---
    try:
        hybrid = HybridRetrieverBase()
        for q in queries[:5]:
            sem, bm = await hybrid.retrieve_per_query(q, top_k=20)
            all_chunks.extend(sem)
            all_chunks.extend(bm)
        print(f"   ✓ BM25/FAISS added, total pool: {len(all_chunks)} chunks")
    except Exception as e:
        print(f"   ⚠ BM25/FAISS fallback failed: {e}")

    # Deduplicate by chunk_id before passing to reranker
    seen = {}
    for c in all_chunks:
        cid = c.get("chunk_id")
        if cid and cid not in seen:
            seen[cid] = c
    deduped = list(seen.values())

    # Tag matched_query for chunks missing it
    for c in deduped:
        if not c.get("matched_query"):
            c["matched_query"] = state["query"]

    # Pack as semantic+bm25 lists for the reranker (split by presence of rrf_score)
    semantic_pool = [c for c in deduped if c.get("similarity_score")]
    bm25_pool = [c for c in deduped if not c.get("similarity_score")]

    return {"retrieved_chunks": [{"semantic": semantic_pool, "bm25": bm25_pool}]}


async def rerank_node(state: ResearchState) -> ResearchState:
    """🚨 CRITICAL GLOBAL RERANK NODE — merges, fuses via RRF, filters, slices top-12."""
    print("⚖️ [RerankNode] Executing Global RRF Fusion & Soft Penalties...")
    packed = state.get("retrieved_chunks", [])
    if not packed:
        return {"reranked_chunks": []}

    all_sem = packed[0].get("semantic", [])
    all_bm = packed[0].get("bm25", [])
    qs = state.get("search_queries", [state["query"]])

    # If we already have RRF-scored chunks from DynamicRetriever, merge them in
    already_scored = [c for c in all_sem if c.get("rrf_score")]
    needs_scoring_sem = [c for c in all_sem if not c.get("rrf_score")]

    if already_scored and not needs_scoring_sem and not all_bm:
        # All chunks already scored by DynamicRetriever's own hybrid pipeline
        reranked = sorted(already_scored, key=lambda x: x.get("rrf_score", 0), reverse=True)[:12]
    else:
        # Merge everything through GlobalReranker
        reranked = GlobalReranker.global_rerank(
            all_bm + [c for c in all_sem if not c.get("rrf_score")],
            [c for c in all_sem if c.get("rrf_score")] + needs_scoring_sem,
            qs,
        )

    # If reranker produced nothing but we have pre-scored chunks, use those
    if not reranked and already_scored:
        reranked = sorted(already_scored, key=lambda x: x.get("rrf_score", 0), reverse=True)[:12]

    # Extract sentence-level evidence for top chunks
    extractor = _get_evidence_extractor()
    main_query = state["query"]
    for c in reranked:
        if not c.get("evidence_sentence"):
            text = c.get("text", "")
            q = c.get("matched_query", main_query)
            ev = extractor.select_best_sentence(q, text)
            c["evidence_sentence"] = ev.get("best_sentence", "")
            c["evidence_score"] = float(ev.get("best_score", 0.0))

    print(f"   ✓ Reranked to {len(reranked)} chunks")
    return {"reranked_chunks": reranked}


async def generate_node(state: ResearchState) -> ResearchState:
    """Use the FULL AnswerGenerator for rich, structured evidence-mapped output."""
    from src.generation.generator import AnswerGenerator

    chunks = state.get("reranked_chunks", [])
    sub_queries = state.get("sub_queries", [])
    query = state["query"]

    generator = AnswerGenerator()

    # Build plan dict matching AnswerGenerator.generate_grouped_answer signature
    plan = {
        "main_question": query,
        "sub_questions": sub_queries,
        "search_queries": state.get("search_queries", []),
        "resolved_user_level": "intermediate",
        "subquestion_intents": {},
    }

    if chunks:
        # Extract paper_facts for comparison matrix
        try:
            from src.retrieval.paper_facts import extract_paper_facts
            chunks = extract_paper_facts(chunks)
        except Exception:
            pass

        grouped_answer = generator.generate_grouped_answer(plan, chunks)
        analysis_data = generator.get_last_analysis()
    else:
        grouped_answer = "No relevant papers or evidence found for this query."
        analysis_data = {}

    return {
        "answer": grouped_answer,
        "evidence_map": {"analysis_data": analysis_data, "plan": plan},
    }


async def verify_node(state: ResearchState) -> ResearchState:
    """Deterministic confidence scoring using the production VerificationAgent."""
    from src.agents.verification import VerificationAgent

    chunks = state.get("reranked_chunks", [])
    evidence_map = state.get("evidence_map", {})
    plan = evidence_map.get("plan", {
        "main_question": state["query"],
        "sub_questions": state.get("sub_queries", []),
    })

    verifier = VerificationAgent()

    # Build the verification input using the established contract
    v_input = VerificationAgent.build_verification_input(
        query=state["query"],
        plan=plan,
        chunks=chunks,
    )

    verification_result = verifier.verify(v_input)

    # Determine expansion need
    confidence = verification_result.get("confidence_score", 0.0)
    needs_expansion = confidence < 0.30 and len(chunks) < 5

    print(f"✅ [VerifierNode] Confidence={confidence:.2f}. Needs expand? {needs_expansion}")

    return {
        "verification": verification_result,
        "needs_expansion": needs_expansion,
    }


async def expand_node(state: ResearchState) -> ResearchState:
    """Generate NEW queries only. Max 1 iteration."""
    cur_iter = state.get("iteration_count", 0)
    print(f"🔄 [ExpandNode] Iteration {cur_iter + 1}")

    llm = _get_llm()
    prompt = (
        f"The query is: {state['query']}. "
        f"Current evidence is weak. Suggest 2 alternative academic search queries "
        f"that target different aspects (datasets, methods, results). "
        f"Return ONLY a JSON array of strings."
    )
    try:
        import re
        raw = llm.generate(prompt)
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        new_q = json.loads(match.group(0)) if match else [state["query"] + " survey"]
    except Exception:
        new_q = [state["query"] + " methods", state["query"] + " evaluation"]

    return {
        "search_queries": state.get("search_queries", []) + new_q,
        "iteration_count": cur_iter + 1,
    }


async def summarize_node(state: ResearchState) -> ResearchState:
    """Use the FULL PipelineSummarizer for structured narrative output."""
    from src.generation.summarizer import PipelineSummarizer

    print("📝 [SummarizeNode] Generating structured narrative summary...")

    llm = _get_llm()
    summarizer = PipelineSummarizer(llm)

    grouped_answer = state.get("answer", "")
    verification = state.get("verification", {})
    evidence_map = state.get("evidence_map", {})
    analysis_data = evidence_map.get("analysis_data", {})

    # Build verification output text
    v_text = ""
    if verification:
        conf = verification.get("confidence_score", verification.get("confidence", 0))
        v_text = f"Confidence: {conf}"

    try:
        summary = summarizer.summarize(
            grouped_answer=grouped_answer,
            verification_output=v_text,
            verification_result=verification,
            analysis_data=analysis_data,
            query=state["query"],
        )
    except Exception as e:
        print(f"   ⚠ Summarizer failed: {e}")
        summary = grouped_answer  # Fallback to raw grouped answer

    return {"final_answer": summary}


# ---------------------------------------------------------
# Graph Definition
# ---------------------------------------------------------

def check_expansion(state: ResearchState) -> str:
    """Conditional routing: expand only if no chunks AND iteration < 1."""
    if state.get("needs_expansion") and state.get("iteration_count", 0) < 1:
        return "expand"
    return "summarize"


def build_research_graph() -> StateGraph:
    workflow = StateGraph(ResearchState)

    workflow.add_node("plan", plan_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("expand", expand_node)
    workflow.add_node("summarize", summarize_node)

    # Strict linear flow
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "retrieve")
    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "generate")
    workflow.add_edge("generate", "verify")

    # Conditional expansion loop
    workflow.add_conditional_edges("verify", check_expansion, {
        "expand": "expand",
        "summarize": "summarize",
    })

    # Expansion loops back to retrieve
    workflow.add_edge("expand", "retrieve")
    workflow.add_edge("summarize", END)

    return workflow.compile()
