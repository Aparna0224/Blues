from typing import TypedDict, List, Dict, Any

class ResearchState(TypedDict):
    """
    STRICT Agentic RAG State Definition.
    Preserves all execution boundaries and controls LangGraph flow.
    """
    query: str
    sub_queries: List[str]
    search_queries: List[str]
    paper_source: str  # Paper source: openalex, semantic_scholar, arxiv, both, all
    retrieved_chunks: List[Dict[str, Any]]
    reranked_chunks: List[Dict[str, Any]]
    evidence_map: Dict[str, Any]
    answer: Any  # Can be string or structured elements mapped before final JSON conversion
    verification: Dict[str, Any]
    needs_expansion: bool
    iteration_count: int
    final_answer: str
