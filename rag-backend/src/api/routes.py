from fastapi import APIRouter

router = APIRouter()

@router.post("/query")
def process_query(query: str):
    return {"query": query, "response": "Processing..."}
