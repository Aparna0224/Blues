"""FastAPI REST API for the RAG pipeline (Stage 6).

Exposes the full Stage 3-5 pipeline as HTTP endpoints so the
React frontend can consume structured JSON instead of CLI text.

Endpoints:
    POST /api/query       — Run the full pipeline on a research question
    POST /api/upload      — Upload a PDF paper for ingestion
    GET  /api/status      — System health / stats
    GET  /api/traces/{id} — Retrieve a saved execution trace
"""

import os
import json
import time
import uuid
import tempfile
import traceback
import re
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import Config
from src.database import get_mongo_client

# ─── App ─────────────────────────────────────────────────────────

from contextlib import asynccontextmanager

_faiss_store = None  # singleton, populated at startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: preload FAISS + BM25 indexes so first query is fast."""
    global _faiss_store
    print("🚀 Blues RAG API starting — preloading indexes...")

    # 1. MongoDB connection
    try:
        mongo = get_mongo_client()
        mongo.connect()
        print("   ✓ MongoDB connected")
    except Exception as e:
        print(f"   ✗ MongoDB connection failed: {e}")

    # 2. FAISS index
    try:
        from src.vector_store import FAISSVectorStore
        _faiss_store = FAISSVectorStore()
        size = _faiss_store.get_index_size()
        print(f"   ✓ FAISS index loaded ({size} vectors)")
    except Exception as e:
        print(f"   ✗ FAISS load failed: {e}")

    # 3. BM25 index (can be slow with large chunk counts)
    try:
        from src.retrieval.bm25_index import get_bm25_index
        bm25 = get_bm25_index()
        if not bm25._is_built:
            print("   ⏳ Building BM25 index from MongoDB in background thread...")
            import threading
            threading.Thread(target=bm25.build_from_mongo, daemon=True).start()
    except Exception as e:
        print(f"   ✗ BM25 load start failed: {e}")

    print("🚀 Startup complete.")
    yield
    print("👋 Blues RAG API shutting down.")


app = FastAPI(
    title=Config.API_TITLE,
    version=Config.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for downloadable report payloads keyed by execution_id.
REPORT_CACHE: dict[str, dict] = {}


def _slugify(value: str, fallback: str = "report") -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:64] or fallback


def _short_timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y%m%d_%H%M")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


# ─── Request / Response models ───────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Research question")
    num_documents: int = Field(default=15, ge=1, le=50, description="Number of documents to retrieve")
    mode: str = Field(default="dynamic", pattern="^(dynamic|cached)$", description="Retrieval mode")
    paper_source: str = Field(
        default=Config.DEFAULT_PAPER_SOURCE,
        pattern="^(openalex|semantic_scholar|arxiv|both|all)$",
        description="Paper source for dynamic retrieval",
    )
    include_summary: bool = Field(default=True, description="Include LLM summary (Stage 5)")
    user_level: Optional[str] = Field(default="auto", description="User level for API request")
    user_id: str = Field(default="local_user", description="User identity for persistent workspace storage")
    project_id: Optional[str] = Field(default=None, description="Optional project id for storing query history")
    filters: Optional[dict] = Field(default=None, description="Optional metadata filters for retrieval")


class QueryResponse(BaseModel):
    query_id: Optional[str] = None
    project_id: Optional[str] = None
    execution_id: str
    query: str
    mode: str
    status: str  # "success" | "error"

    # Stage 3 — Planning
    planning: dict

    # Stage 3 — Retrieval + Grouped answer
    grouped_answer: str
    chunks_used: int
    papers_found: list

    # Stage 4 — Verification
    verification: dict

    # Stage 5 — LLM summary (optional)
    summary: Optional[str] = None

    # Timing
    total_time_ms: float

    # Errors (if any non-fatal)
    warnings: list = []


class StatusResponse(BaseModel):
    mongodb: str
    papers_count: int
    chunks_count: int
    faiss_vectors: int
    llm_provider: str
    llm_model: str


class UploadResponse(BaseModel):
    status: str
    paper_id: str
    title: str
    chunks_created: int
    vectors_added: int


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default="")
    user_id: str = Field(default="local_user")


class ProjectResponse(BaseModel):
    project_id: str
    user_id: str
    name: str
    description: str
    is_archived: bool
    created_at: str
    updated_at: str


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)


class HardDeleteProjectResponse(BaseModel):
    status: str
    project_id: str
    project_deleted: int
    queries_deleted: int
    query_results_deleted: int
    traces_deleted: int


class QueryHistoryItem(BaseModel):
    query_id: str
    project_id: str
    user_id: str
    query_text: str
    mode: str
    paper_source: str
    user_level: str
    status: str
    execution_id: str
    chunks_used: int
    papers_found: int
    created_at: str


# ─── POST /api/query ─────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
async def run_query(req: QueryRequest):
    """Run the full agentic RAG pipeline and return structured JSON."""
    import time as _time
    from src.trace.tracer import ExecutionTracer

    t_start = _time.perf_counter()
    warnings: list[str] = []

    mode = req.mode
    tracer = ExecutionTracer(query=req.query, mode=mode)

    # ── Connect MongoDB ──────────────────────────────────────────
    try:
        mongo = get_mongo_client()
        mongo.connect()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")

    user_id = (req.user_id or "local_user").strip() or "local_user"
    selected_project = None
    if req.project_id:
        selected_project = mongo.get_projects_collection().find_one(
            {"project_id": req.project_id, "user_id": user_id, "is_archived": {"$ne": True}},
            {"_id": 0},
        )
    if not selected_project:
        selected_project = mongo.ensure_default_project(user_id=user_id)
    project_id = selected_project.get("project_id")

    # ── Step 1: LangGraph Execution ────────────────────────────────
    from src.orchestration.graph import build_research_graph
    
    app_graph = build_research_graph()
    initial_state = {
        "query": req.query,
        "sub_queries": [],
        "search_queries": [],
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "evidence_map": {},
        "answer": "",
        "verification": {},
        "needs_expansion": False,
        "iteration_count": 0,
        "final_answer": ""
    }

    try:
        final_state = await app_graph.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")

    # Extract Agentic RAG state variables (restored full pipeline)
    sub_questions = final_state.get("sub_queries", [])
    search_queries = final_state.get("search_queries", [req.query])
    chunks = final_state.get("reranked_chunks", [])

    # answer is now a string from AnswerGenerator.generate_grouped_answer
    grouped_answer = final_state.get("answer", "")
    if not isinstance(grouped_answer, str):
        grouped_answer = str(grouped_answer)

    verification_result = final_state.get("verification", {})
    summary_text = final_state.get("final_answer")  # From PipelineSummarizer

    # analysis_data is stored in evidence_map by generate_node
    evidence_map = final_state.get("evidence_map", {})
    analysis_data = evidence_map.get("analysis_data", {})

    # Collect warnings safely
    if isinstance(verification_result, dict):
        warnings.extend(verification_result.get("penalties", verification_result.get("warnings", [])))
    
    # Optional: Fill tracer for existing UI expectation
    try:
        tracer.record_planning(
            input_question=req.query,
            sub_questions=sub_questions,
            search_queries=search_queries,
            llm_raw_output=json.dumps({"sub_questions": sub_questions, "search_queries": search_queries}),
            latency_ms=0,
        )
        tracer.record_evidence_selection(
            claims_used=[
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "claim": c.get("evidence_sentence", c.get("text", "")[:200]),
                    "similarity_score": c.get("similarity_score", 0),
                    "paper_id": c.get("paper_id", "")
                } for c in chunks
            ]
        )
        if verification_result:
            tracer.record_verification(verification_result)
    except Exception as e:
        pass

    # ── Collect unique papers (look up metadata from MongoDB) ────
    seen_paper_ids: set = set()
    for c in chunks:
        pid = c.get("paper_id", "")
        if pid:
            seen_paper_ids.add(pid)

    papers_found: list[dict] = []
    if seen_paper_ids:
        try:
            papers_col = mongo.get_papers_collection()
            paper_docs = papers_col.find(
                {"paper_id": {"$in": list(seen_paper_ids)}},
                {"_id": 0, "paper_id": 1, "title": 1, "authors": 1, "year": 1, "doi": 1},
            )
            for doc in paper_docs:
                authors_raw = doc.get("authors", "Unknown")
                if isinstance(authors_raw, list):
                    authors_str = ", ".join(str(a) for a in authors_raw)
                else:
                    authors_str = str(authors_raw) if authors_raw else "Unknown"
                papers_found.append({
                    "paper_id": doc.get("paper_id", ""),
                    "title": doc.get("title", "Unknown"),
                    "authors": authors_str,
                    "year": str(doc.get("year", "")),
                    "doi": doc.get("doi", ""),
                })
        except Exception:
            # Fallback: just list paper_ids
            for pid in seen_paper_ids:
                papers_found.append({
                    "paper_id": pid,
                    "title": "Unknown",
                    "authors": "Unknown",
                    "year": "",
                    "doi": "",
                })

    # ── Save trace ───────────────────────────────────────────────
    execution_id = tracer.execution_id

    if analysis_data:
        analysis_data["query"] = req.query
        analysis_data["generated_at"] = datetime.now(timezone.utc).isoformat()
        analysis_data["final_summary"] = summary_text or ""
        # Enrich references from papers_found when available (DOI/link mandatory in export).
        paper_lookup = {p.get("paper_id", ""): p for p in papers_found}
        for ref in analysis_data.get("references", []):
            pid = ref.get("paper_id", "")
            doc = paper_lookup.get(pid, {})
            if doc:
                ref["title"] = doc.get("title", ref.get("title", "Unknown"))
                ref["year"] = doc.get("year", ref.get("year", "N/A"))
                ref["doi"] = ref.get("doi") or doc.get("doi", "")
                if not ref.get("link") and doc.get("doi"):
                    ref["link"] = f"https://doi.org/{doc.get('doi')}"

        REPORT_CACHE[execution_id] = analysis_data

    try:
        tracer.save_trace(directory="output")
    except Exception:
        pass
    try:
        trace = tracer.finalize()
        mongo.store_trace(trace)
    except Exception:
        pass

    total_ms = round((_time.perf_counter() - t_start) * 1000, 1)

    query_id = f"qry_{uuid.uuid4().hex[:16]}"

    response_payload = QueryResponse(
        query_id=query_id,
        project_id=project_id,
        execution_id=execution_id,
        query=req.query,
        mode=mode,
        status="success",
        planning={
            "main_question": req.query,
            "sub_questions": sub_questions,
            "search_queries": search_queries,
            "latency_ms": 0,
        },
        grouped_answer=grouped_answer,
        chunks_used=len(chunks),
        papers_found=papers_found,
        verification=verification_result,
        summary=summary_text,
        total_time_ms=total_ms,
        warnings=warnings,
    )

    # Persist query + full result for project history / reopen workflow
    try:
        now = datetime.now(timezone.utc).isoformat()
        query_doc = {
            "query_id": query_id,
            "project_id": project_id,
            "user_id": user_id,
            "query_text": req.query,
            "mode": mode,
            "paper_source": req.paper_source,
            "user_level": req.user_level or "auto",
            "status": "completed",
            "execution_id": execution_id,
            "chunks_used": len(chunks),
            "papers_found": len(papers_found),
            "created_at": now,
            "updated_at": now,
        }
        result_doc = {
            "query_id": query_id,
            "execution_id": execution_id,
            "project_id": project_id,
            "user_id": user_id,
            "result_payload": response_payload.model_dump(),
            "retrieval_stats": {
                "chunks_used": len(chunks),
                "papers_found": len(papers_found),
                "sub_questions": len(sub_questions),
            },
            "quality_flags": {
                "warnings": warnings,
                "verification_confidence": verification_result.get("confidence_score") if verification_result else None,
            },
            "created_at": now,
            "updated_at": now,
        }
        mongo.store_query_run(query_doc=query_doc, result_doc=result_doc)

        mongo.get_projects_collection().update_one(
            {"project_id": project_id},
            {"$set": {"updated_at": now}},
        )
    except Exception as e:
        # Non-fatal: query completed successfully even if persistence fails
        response_payload.warnings.append(f"Workspace persistence failed: {e}")

    return response_payload


@app.post("/api/projects/{project_id}/queries", response_model=QueryResponse)
async def run_project_query(project_id: str, req: QueryRequest):
    """Run query scoped to a project and persist under that project id."""
    scoped_req = req.model_copy(update={"project_id": project_id})
    return await run_query(scoped_req)


@app.get("/api/download-report")
async def download_report(
    format: str = Query(default="pdf", pattern="^(pdf|md)$"),
    execution_id: str = Query(..., min_length=6),
    project_name: str | None = Query(default=None),
    query_text: str | None = Query(default=None),
    generated_at: str | None = Query(default=None),
):
    """Download a comprehensive report in PDF or Markdown format for a completed execution."""
    from src.export.report_builder import ReportBuilder

    analysis = REPORT_CACHE.get(execution_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Report data not found for execution_id. Re-run query and try download again.",
        )

    analysis_for_report = dict(analysis)
    effective_query = (query_text or analysis_for_report.get("query") or "Research Query").strip()
    effective_generated_at = generated_at or analysis_for_report.get("generated_at") or datetime.now(timezone.utc).isoformat()

    analysis_for_report["query"] = effective_query
    analysis_for_report["generated_at"] = effective_generated_at
    analysis_for_report["project_name"] = (project_name or analysis_for_report.get("project_name") or "Untitled Project").strip()
    analysis_for_report["report_title"] = effective_query

    builder = ReportBuilder(system_name="Blues")
    file_stem = f"{_slugify(effective_query, fallback='query')}_{_short_timestamp(effective_generated_at)}"

    if format == "md":
        body = builder.build_markdown(analysis_for_report).encode("utf-8")
        return Response(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={file_stem}.md"},
        )

    body = builder.build_pdf(analysis_for_report)
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_stem}.pdf"},
    )


# ─── POST /api/upload ────────────────────────────────────────────

@app.post("/api/upload", response_model=UploadResponse)
async def upload_paper(file: UploadFile = File(...)):
    """Upload a PDF paper, ingest it, chunk, embed, and index it."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        mongo = get_mongo_client()
        mongo.connect()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")

    # Save uploaded file to temp location
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Extract text from PDF
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(tmp_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {e}")
    finally:
        # Cleanup temp file
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="PDF contains no extractable text.")

    # Create paper document
    paper_id = f"upload_{uuid.uuid4().hex[:12]}"
    title = file.filename.replace(".pdf", "").replace("_", " ").replace("-", " ")
    paper = {
        "paper_id": paper_id,
        "title": title,
        "abstract": full_text[:2000],  # First 2000 chars as abstract
        "full_text": full_text,
        "authors": "Uploaded by user",
        "year": "",
        "doi": "",
        "source": "user_upload",
        "openalex_id": "",
    }

    # Store paper in MongoDB
    try:
        papers_col = mongo.get_papers_collection()
        papers_col.replace_one({"paper_id": paper_id}, paper, upsert=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store paper: {e}")

    # Chunk the paper
    try:
        from src.chunking.processor import TextChunker

        chunker = TextChunker()
        chunks = chunker.create_chunks([paper])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {e}")

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks created from the PDF.")

    # Store chunks in MongoDB
    try:
        chunks_col = mongo.get_chunks_collection()
        for chunk in chunks:
            chunks_col.replace_one({"chunk_id": chunk["chunk_id"]}, chunk, upsert=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store chunks: {e}")

    # Generate embeddings and add to FAISS
    vectors_added = 0
    try:
        from src.embeddings.embedder import get_shared_embedder
        from src.vector_store import FAISSVectorStore

        embedder = get_shared_embedder()
        embedded_chunks = embedder.generate_chunk_embeddings(chunks)

        vector_store = FAISSVectorStore()
        import numpy as np

        embeddings_array = np.array([c["embedding"] for c in embedded_chunks])
        chunk_ids = [c["chunk_id"] for c in embedded_chunks]
        vector_store.add_embeddings(embeddings_array, chunk_ids)
        vector_store.save_index()
        vectors_added = len(chunk_ids)
    except Exception as e:
        # Non-fatal: paper is stored but not indexed
        pass

    return UploadResponse(
        status="success",
        paper_id=paper_id,
        title=title,
        chunks_created=len(chunks),
        vectors_added=vectors_added,
    )


# ─── GET /api/status ─────────────────────────────────────────────

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Return system health and statistics."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        papers_count = mongo.get_papers_collection().count_documents({})
        chunks_count = mongo.get_chunks_collection().count_documents({})
        mongodb_status = "connected"
    except Exception:
        papers_count = 0
        chunks_count = 0
        mongodb_status = "disconnected"

    try:
        if _faiss_store:
            faiss_vectors = _faiss_store.get_index_size()
        else:
            from src.vector_store import FAISSVectorStore
            faiss_vectors = FAISSVectorStore().get_index_size()
    except Exception:
        faiss_vectors = 0

    model = ""
    if Config.LLM_PROVIDER == "groq":
        model = Config.GROQ_MODEL
    elif Config.LLM_PROVIDER == "gemini":
        model = Config.GEMINI_MODEL
    else:
        model = Config.OLLAMA_MODEL

    return StatusResponse(
        mongodb=mongodb_status,
        papers_count=papers_count,
        chunks_count=chunks_count,
        faiss_vectors=faiss_vectors,
        llm_provider=Config.LLM_PROVIDER,
        llm_model=model,
    )


# ─── GET /api/traces/{execution_id} ──────────────────────────────

@app.get("/api/traces/{execution_id}")
async def get_trace(execution_id: str):
    """Retrieve a saved execution trace."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")

    trace = mongo.get_trace(execution_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


# ─── Workspace Persistence Endpoints ────────────────────────────

@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(req: ProjectCreateRequest):
    """Create a persistent project for query history and reopen flows."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")

    now = datetime.now(timezone.utc).isoformat()
    project = {
        "project_id": f"proj_{uuid.uuid4().hex[:12]}",
        "user_id": req.user_id,
        "name": req.name.strip(),
        "description": (req.description or "").strip(),
        "is_archived": False,
        "created_at": now,
        "updated_at": now,
    }
    mongo.get_projects_collection().insert_one(project)
    return ProjectResponse(**project)


@app.get("/api/projects", response_model=list[ProjectResponse])
async def list_projects(
    user_id: str = Query(default="local_user"),
    include_archived: bool = Query(default=False),
):
    """List projects for a given user."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        projects = mongo.list_projects(user_id=user_id, include_archived=include_archived)
        if not projects and not include_archived:
            projects = [mongo.ensure_default_project(user_id=user_id)]
        return [ProjectResponse(**p) for p in projects]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get a single project by id."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        project = mongo.get_projects_collection().find_one({"project_id": project_id, "is_archived": {"$ne": True}}, {"_id": 0})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return ProjectResponse(**project)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.patch("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, req: ProjectUpdateRequest, user_id: str = Query(default="local_user")):
    """Update a project's mutable fields (name/description)."""
    if req.name is None and req.description is None:
        raise HTTPException(status_code=400, detail="At least one field is required: name or description")

    try:
        mongo = get_mongo_client()
        mongo.connect()
        updated = mongo.update_project(
            project_id,
            user_id=user_id,
            name=req.name.strip() if req.name is not None else None,
            description=req.description.strip() if req.description is not None else None,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Project not found")
        return ProjectResponse(**updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.delete("/api/projects/{project_id}")
async def archive_project(project_id: str, user_id: str = Query(default="local_user")):
    """Archive a project (soft delete) while preserving its historical records."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        archived = mongo.archive_project(project_id, user_id=user_id)
        if not archived:
            raise HTTPException(status_code=404, detail="Project not found")
        mongo.ensure_default_project(user_id=user_id)
        return {"status": "archived", "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.post("/api/projects/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(project_id: str, user_id: str = Query(default="local_user")):
    """Restore a previously archived project."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        restored = mongo.restore_project(project_id, user_id=user_id)
        if not restored:
            raise HTTPException(status_code=404, detail="Archived project not found")
        project = mongo.get_projects_collection().find_one(
            {"project_id": project_id, "user_id": user_id, "is_archived": {"$ne": True}},
            {"_id": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found after restore")
        return ProjectResponse(**project)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.delete("/api/projects/{project_id}/hard", response_model=HardDeleteProjectResponse)
async def hard_delete_project(
    project_id: str,
    user_id: str = Query(default="local_user"),
    confirm: bool = Query(default=False),
):
    """Permanently delete a project and all persisted records tied to it."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Hard delete requires confirm=true")

    try:
        mongo = get_mongo_client()
        mongo.connect()
        deleted = mongo.hard_delete_project(project_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")

        mongo.ensure_default_project(user_id=user_id)

        return HardDeleteProjectResponse(
            status="hard_deleted",
            project_id=project_id,
            project_deleted=deleted["project_deleted"],
            queries_deleted=deleted["queries_deleted"],
            query_results_deleted=deleted["query_results_deleted"],
            traces_deleted=deleted["traces_deleted"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.get("/api/projects/{project_id}/queries", response_model=list[QueryHistoryItem])
async def list_project_queries(project_id: str):
    """List queries for a project (history panel)."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        items = mongo.list_project_queries(project_id)
        return [QueryHistoryItem(**item) for item in items]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.get("/api/queries/{query_id}")
async def get_query(query_id: str):
    """Retrieve query metadata by query id."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        item = mongo.get_queries_collection().find_one({"query_id": query_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Query not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.get("/api/queries/{query_id}/result", response_model=QueryResponse)
async def get_query_result(query_id: str):
    """Retrieve full persisted output for a stored query id."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        result = mongo.get_query_result(query_id)
        if not result:
            raise HTTPException(status_code=404, detail="Query result not found")
        payload = result.get("result_payload") or {}
        return QueryResponse(**payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")


@app.get("/api/executions/{execution_id}/result", response_model=QueryResponse)
async def get_execution_result(execution_id: str):
    """Retrieve full persisted output by execution id."""
    try:
        mongo = get_mongo_client()
        mongo.connect()
        result = mongo.get_query_result_by_execution(execution_id)
        if not result:
            raise HTTPException(status_code=404, detail="Execution result not found")
        payload = result.get("result_payload") or {}
        return QueryResponse(**payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unavailable: {e}")
