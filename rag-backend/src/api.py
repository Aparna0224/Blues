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

app = FastAPI(
    title=Config.API_TITLE,
    version=Config.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
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
    include_summary: bool = Field(default=True, description="Include LLM summary (Stage 5)")
    user_level: Optional[str] = Field(default="auto", description="User level for API request")
    filters: Optional[dict] = Field(default=None, description="Optional metadata filters for retrieval")


class QueryResponse(BaseModel):
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


# ─── POST /api/query ─────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
async def run_query(req: QueryRequest):
    """Run the full agentic RAG pipeline and return structured JSON."""
    import time as _time

    from src.llm.factory import get_llm
    from src.agents.planner import PlannerAgent
    from src.agents.verification import VerificationAgent
    from src.generation.generator import AnswerGenerator
    from src.retrieval.retriever import Retriever
    from src.trace.tracer import ExecutionTracer
    from src.generation.summarizer import PipelineSummarizer

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

    # ── Step 1: LLM + Planner ────────────────────────────────────
    try:
        llm = get_llm()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM init failed: {e}")

    planner = PlannerAgent(llm)

    try:
        t0 = _time.perf_counter()
        plan = planner.plan(req.query, req.user_level or "auto")
        planning_ms = round((_time.perf_counter() - t0) * 1000, 1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {e}")

    if not plan:
        raise HTTPException(status_code=500, detail="Planner returned empty plan")

    sub_questions = plan.get("sub_questions", [])
    search_queries = plan.get("search_queries", [req.query])

    tracer.record_planning(
        input_question=req.query,
        sub_questions=sub_questions,
        search_queries=search_queries,
        llm_raw_output=plan.get("_raw_output", ""),
        latency_ms=planning_ms,
    )

    # Scale top_k for agentic queries: each sub-question needs its own evidence
    effective_top_k = max(req.num_documents, len(sub_questions) * 5, 15)

    # ── Step 2: Retrieval ────────────────────────────────────────
    chunks = []
    try:
        if mode == "dynamic":
            from src.retrieval.dynamic_retriever import DynamicRetriever

            dynamic_retriever = DynamicRetriever(use_evidence=True, papers_per_query=5)
            chunks = dynamic_retriever.dynamic_retrieve(
                search_queries=search_queries,
                main_query=req.query,
                top_k=effective_top_k,
                metadata_filters=req.filters,
            )
        else:
            # Cached mode: use hybrid retrieval if enabled
            if Config.HYBRID_RETRIEVAL_ENABLED:
                from src.retrieval.hybrid_retriever import HybridRetriever

                hybrid_retriever = HybridRetriever(use_evidence=True)
                chunks = hybrid_retriever.multi_retrieve(
                    search_queries,
                    top_k_per_query=max(5, len(sub_questions) * 3),
                    max_total=effective_top_k,
                    metadata_filters=req.filters,
                )
            else:
                retriever = Retriever(use_evidence=True)
                chunks = retriever.multi_retrieve(
                    search_queries,
                    top_k_per_query=max(5, len(sub_questions) * 3),
                    max_total=effective_top_k,
                    metadata_filters=req.filters,
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {e}")

    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant chunks found for any search query.")

    unique_paper_ids = {c.get("paper_id") for c in chunks if c.get("paper_id")}
    if len(unique_paper_ids) < Config.MIN_UNIQUE_PAPERS_FOR_CLAIMS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Insufficient source diversity for claim generation: "
                f"found {len(unique_paper_ids)} unique paper(s), "
                f"requires at least {Config.MIN_UNIQUE_PAPERS_FOR_CLAIMS}. "
                "Please broaden the query, increase documents, or switch retrieval mode."
            ),
        )

    # Build per-query retrieval trace
    per_query_trace = []
    for sq in search_queries:
        matching = [
            c for c in chunks
            if (c.get("matched_query") == sq) or (c.get("search_query") == sq)
        ]
        per_query_trace.append(
            {
                "search_query": sq,
                "top_k": req.num_documents,
                "retrieved_chunk_ids": [c.get("chunk_id", "") for c in matching[:5]],
                "similarity_scores": [c.get("similarity_score", 0) for c in matching[:5]],
            }
        )
    tracer.record_retrieval(
        per_query=per_query_trace,
        total_chunks_before_merge=len(chunks),
        unique_chunks_after_merge=len({c.get("chunk_id", i) for i, c in enumerate(chunks)}),
    )

    # ── Step 3: Grouped answer ───────────────────────────────────
    try:
        generator = AnswerGenerator()
        grouped_answer = generator.generate_grouped_answer(plan, chunks)
        analysis_data = generator.get_last_analysis() if hasattr(generator, "get_last_analysis") else {}
        # Ensure analysis_data is never None
        if not analysis_data or not isinstance(analysis_data, dict):
            analysis_data = {
                "query": req.query,
                "grouped_answer": grouped_answer,
                "chunks_used": len(chunks),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer generation failed: {e}")

    tracer.record_evidence_selection(
        claims_used=[
            {
                "chunk_id": c.get("chunk_id", ""),
                "claim": c.get("evidence_sentence", c.get("text", "")[:200]),
                "similarity_score": c.get("similarity_score", 0),
                "paper_id": c.get("paper_id", ""),
                "sub_question": "",
            }
            for c in chunks
        ]
    )

    # ── Step 4: Verification ─────────────────────────────────────
    verification_result = {}
    verification_output = ""
    try:
        verifier = VerificationAgent()
        verification_input = verifier.build_verification_input(req.query, plan, chunks)
        verification_result = verifier.verify(verification_input)
        verification_output = verifier.format_verification_output(verification_result)
    except Exception as e:
        warnings.append(f"Verification failed: {e}")
        verification_result = {}

    if verification_result:
        tracer.record_verification(verification_result)
        audit = verification_result.get("audit", {})
        tracer.record_filtering(
            total_claims_received=audit.get("total_claims_received", 0),
            after_deduplication=audit.get("claims_after_dedup", 0),
            after_relevance_filter=audit.get("claims_after_relevance_filter", 0),
            above_similarity_threshold=audit.get("claims_above_similarity_threshold", 0),
            claims_rejected=audit.get("claims_rejected", 0),
        )

    # ── Step 5: LLM Summary (optional) ───────────────────────────
    summary_text: Optional[str] = None
    if req.include_summary:
        try:
            summarizer = PipelineSummarizer(llm)
            summary_text = summarizer.summarize(
                grouped_answer=grouped_answer,
                verification_output=verification_output,
                verification_result=verification_result,
                analysis_data=analysis_data,
                query=req.query,
            )
        except Exception as e:
            warnings.append(f"Summary generation failed: {e}")

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

    # Build comprehensive report cache with all necessary fields
    report_data = {
        "query": req.query,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_id": execution_id,
        "grouped_answer": grouped_answer,
        "verification": verification_result,
        "final_summary": summary_text or "",
        "planning": plan,
        "chunks_used": len(chunks),
        "papers_found": papers_found,
    }
    
    # Merge in any analysis data from generator
    if analysis_data and isinstance(analysis_data, dict):
        report_data.update(analysis_data)
    
    # Build references list from papers_found
    paper_lookup = {p.get("paper_id", ""): p for p in papers_found}
    references = []
    for p in papers_found:
        pid = p.get("paper_id", "")
        ref = {
            "paper_id": pid,
            "title": p.get("title", "Unknown"),
            "authors": p.get("authors", "Unknown"),
            "year": p.get("year", ""),
            "doi": p.get("doi", ""),
            "link": f"https://doi.org/{p.get('doi')}" if p.get("doi") else "",
        }
        references.append(ref)
    report_data["references"] = references
    
    # Store in cache for download endpoint
    REPORT_CACHE[execution_id] = report_data

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

    return QueryResponse(
        execution_id=execution_id,
        query=req.query,
        mode=mode,
        status="success",
        planning={
            "main_question": plan.get("main_question", req.query),
            "sub_questions": sub_questions,
            "search_queries": search_queries,
            "latency_ms": planning_ms,
        },
        grouped_answer=grouped_answer,
        chunks_used=len(chunks),
        papers_found=papers_found,
        verification=verification_result,
        summary=summary_text,
        total_time_ms=total_ms,
        warnings=warnings,
    )


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
        from src.vector_store import FAISSVectorStore

        vs = FAISSVectorStore()
        faiss_vectors = vs.get_index_size()
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
