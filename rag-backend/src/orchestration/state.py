# FILE: src/orchestration/state.py
from typing import Optional, List, TypedDict

class ResearchState(TypedDict):
    """
    Shared state object for the LangGraph agentic pipeline.
    Passed through every node during execution.
    """
    query: str
    user_level: str
    plan: Optional[dict]          # populated by plan_node
    chunks: List[dict]            # populated/expanded by retrieve_node / expand_node
    answer: Optional[str]         # populated by generate_node
    confidence: Optional[float]   # populated by verify_node
    conflicts: List[dict]         # populated by generate_node
    retry_count: int              # incremented by expand_node (max 2)
    warnings: List[str]           # populated by verify_node
    trace: dict                   # appended by every node
    should_expand: bool           # set by verify_node, read by router
