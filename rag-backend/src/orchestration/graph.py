# FILE: src/orchestration/graph.py
import asyncio
from typing import TypedDict
from langgraph.graph import StateGraph, END
from src.orchestration.state import ResearchState

# We will let api.py wire in the actual agents or dependencies via a factory/closure,
# or we can import them directly if we assume singleton/factory pattern usage.

from src.llm.factory import get_llm
from src.agents.planner import PlannerAgent
from src.agents.verification import VerificationAgent
from src.generation.generator import AnswerGenerator
from src.generation.summarizer import PipelineSummarizer
from src.config import Config

async def plan_node(state: ResearchState) -> dict:
    """Decompose the question into sub-questions."""
    llm = get_llm()
    planner = PlannerAgent(llm)
    
    plan = planner.plan(state["query"], state.get("user_level", "auto"))
    
    # We append a trace fragment to easily extract it later
    return {"plan": plan}

async def retrieve_node(state: ResearchState) -> dict:
    """Retrieve chunks based on the plan."""
    plan = state.get("plan", {})
    search_queries = plan.get("search_queries", [state["query"]])
    
    # Mode handling would typically be injected, assuming dynamic by default
    # To keep the signature clean, we can rely on Config or state variables.
    from src.retrieval.dynamic_retriever import DynamicRetriever
    retriever = DynamicRetriever(use_evidence=True, papers_per_query=5)
    
    chunks = await retriever.retrieve(search_queries)
    return {"chunks": chunks}

async def generate_node(state: ResearchState) -> dict:
    """Extract evidence, detect conflicts, and synthesize a structured grouped answer."""
    generator = AnswerGenerator()
    grouped_answer = generator.generate_grouped_answer(state.get("plan", {}), state.get("chunks", []))
    
    # In full system, AnswerGenerator does the conflict detection internally or delegates it.
    conflicts = getattr(generator, "last_conflicts", [])
    analysis_data = generator.get_last_analysis()
    
    return {"answer": grouped_answer, "conflicts": conflicts, "analysis_data": analysis_data}

async def verify_node(state: ResearchState) -> dict:
    """Deterministically score confidence and set expansion flag if low."""
    verifier = VerificationAgent()
    
    ver_input = verifier.build_verification_input(state["query"], state.get("plan", {}), state.get("chunks", []))
    result = verifier.verify(ver_input)
    
    confidence = result.get("confidence_score", 0.0)
    warnings = result.get("warnings", [])
    
    chunks_len = len(state.get("chunks", []))
    retry_count = state.get("retry_count", 0)
    
    should_expand = False
    if confidence < 0.45 and chunks_len < 10 and retry_count < 2:
        should_expand = True
        
    return {
        "confidence": confidence,
        "warnings": state.get("warnings", []) + warnings,
        "should_expand": should_expand,
        "verification_result": result  # Adding this so we can access it on summarization
    }

def route_after_verify(state: ResearchState) -> str:
    """Conditional routing based on should_expand flag."""
    if state["should_expand"] and state["retry_count"] < 2:
        return "expand"
    return "summarize"

async def expand_node(state: ResearchState) -> dict:
    """Expand search queries and retrieve more chunks."""
    plan = state.get("plan", {})
    search_queries = plan.get("search_queries", [state["query"]])
    
    expanded_queries = [sq + " (broadened)" for sq in search_queries] # Simple heuristic
    
    from src.retrieval.dynamic_retriever import DynamicRetriever
    retriever = DynamicRetriever(use_evidence=True, papers_per_query=5)
    new_chunks = await retriever.retrieve(expanded_queries, use_web_fallback=True)
    
    # Merge and deduplicate by chunk_id
    existing_chunks = state.get("chunks", [])
    seen = {c["chunk_id"] for c in existing_chunks}
    merged_chunks = list(existing_chunks)
    
    for nc in new_chunks:
        if nc["chunk_id"] not in seen:
            seen.add(nc["chunk_id"])
            merged_chunks.append(nc)
            
    return {
        "chunks": merged_chunks,
        "retry_count": state.get("retry_count", 0) + 1
    }

async def summarize_node(state: ResearchState) -> dict:
    """Generate LLM narrative summary."""
    llm = get_llm()
    summarizer = PipelineSummarizer(llm)
    
    summary = summarizer.summarize(
        grouped_answer=state.get("answer", ""),
        verification_output=str(state.get("verification_result", {})), # Placeholder mapping
        verification_result=state.get("verification_result", {}),
        analysis_data=state.get("analysis_data", {}),
        query=state["query"]
    )
    
    # The summary text itself isn't stored in the typed dict as per prompt definition
    # but we can return it inside "trace" or update a custom field. 
    # For now, we will add it to the state output dynamically since dictionaries are mutable.
    return {"summary": summary}

def build_research_graph() -> StateGraph:
    """Build and compile the LangGraph for the RAG pipeline."""
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("plan", plan_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("expand", expand_node)
    workflow.add_node("summarize", summarize_node)
    
    workflow.set_entry_point("plan")
    
    workflow.add_edge("plan", "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "verify")
    
    workflow.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "expand": "expand",
            "summarize": "summarize"
        }
    )
    
    workflow.add_edge("expand", "generate")
    workflow.add_edge("summarize", END)
    
    return workflow.compile()
