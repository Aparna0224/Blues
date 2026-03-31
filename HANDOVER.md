# Blues RAG Project — Handover Document

## 1) Project Overview
Blues is an XAI‑enhanced, agentic RAG research assistant focused on rigorous evidence grounding. The system ingests papers, builds embeddings, retrieves evidence, generates answers with citations, verifies claims, and logs a full trace of reasoning.

**Key goals**
- Claim‑to‑sentence grounding and evidence scoring.
- Explicit uncertainty signaling and verification metrics.
- Full traceability (planning → retrieval → evidence selection → verification).
- Support for local LLMs (Ollama) and hosted LLMs (Groq / Gemini).

## 2) Repository Structure
```
D:\Project\Blues\
├── rag-backend\            # Python FastAPI + CLI + RAG pipeline
└── rag-frontend\           # React + Vite UI
```

## 3) Architecture by Stage
### Stage 1 — Core RAG
- Ingests papers (OpenAlex + Semantic Scholar)
- Chunking + embeddings (SciBERT)
- FAISS search

### Stage 2 — Evidence Extraction
- Sentence‑level evidence via NLTK + SciBERT similarity
- Evidence scores attached per chunk

### Stage 3 — Planner Agent
- Query decomposition into sub‑questions + search queries
- Dynamic retrieval mode to fetch fresh papers

### Stage 4 — Verification Agent
- Deterministic confidence scoring
- Claim filtering / dedup / similarity threshold gating
- Conflict detection

### Stage 5 — Trace Layer
- JSON trace of planning, retrieval, filtering, verification
- Stored in MongoDB and output/ traces

### Stage 6 — UI
- React UI for query + metrics + summaries
- Metadata filters and advanced options in query form

## 4) Backend Setup (rag-backend)
### Requirements
- Python 3.11+
- uv package manager
- MongoDB Atlas connection

### Install & Run
1. Create and activate env
- `uv venv`
- `\.venv\Scripts\Activate.ps1`

2. Install deps
- `uv pip sync pyproject.toml`

3. Configure `.env`
- `MONGO_URI` (Atlas URI with real password)
- `LLM_PROVIDER` (local | groq | gemini)
- API keys (Groq/Gemini/OpenAlex/Semantic Scholar)

4. Run API server
- `uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload`

### CLI Commands
- Ingest papers:
  - `uv run python -m src.main ingest --query "machine learning" --max-results 10`
- Build FAISS index:
  - `uv run python -m src.main build-index`
- Query (basic):
  - `uv run python -m src.main query --query "..." --top-k 5`
- Query (evidence):
  - `uv run python -m src.main query --query "..." --evidence`
- Agentic query (static):
  - `uv run python -m src.main query --query "..." --plan`
- Agentic query (dynamic):
  - `uv run python -m src.main query --query "..." --plan --dynamic`

### CLI Metadata Filters (new)
- `--filter-section` (abstract | body)
- `--filter-category`
- `--filter-tags` (comma‑separated)
- `--filter-year-min` / `--filter-year-max`
- `--filter-title-contains`
- `--filter-source` (openalex | semantic_scholar)

## 5) Frontend Setup (rag-frontend)
### Requirements
- Node.js 18+
- npm 9+

### Install & Run
- `npm install`
- `npm run dev`

Frontend is served at `http://localhost:5173` and proxies `/api` to `http://localhost:8000`.

## 6) Core Modules (Backend)
### Ingestion
- `src/ingestion/loader.py` (OpenAlex + Semantic Scholar)
- `src/ingestion/fulltext.py` (PDF / HTML / Unpaywall / PMC)

### Chunking + Metadata Enrichment
- `src/chunking/processor.py`
- Adds `metadata` to each chunk:
  - title, year, section, summary, tags, category, source

### Retrieval
- `src/retrieval/retriever.py` (static FAISS)
- `src/retrieval/dynamic_retriever.py` (live paper fetch)
- Filtering logic:
  - similarity threshold
  - keyword overlap filter
  - domain keyword gate
  - metadata filters (section/category/tags/year/title/source)

### Evidence
- `src/evidence/extractor.py` (sentence similarity, evidence score)

### Generation + Verification
- `src/generation/generator.py`
- `src/agents/verification.py`

### Trace
- `src/trace/tracer.py` (JSON trace)

## 7) API Surface (FastAPI)
Endpoint: `POST /api/query`
Request body:
- `query`: string
- `num_documents`: int
- `mode`: "dynamic" | "cached"
- `include_summary`: bool
- `filters`: optional metadata filter object

Endpoint: `POST /api/upload`
- Upload PDF for ingestion

Endpoint: `GET /api/status`
- Returns MongoDB + FAISS stats

Endpoint: `GET /api/traces/{id}`
- Retrieve trace JSON

## 8) Metadata Filters (API + UI)
Example request body:
```
{
  "query": "RAG in research assistance",
  "num_documents": 15,
  "mode": "dynamic",
  "include_summary": true,
  "filters": {
    "section": "abstract",
    "category": "rag",
    "tags": ["retrieval", "grounding"],
    "year": {"min": 2020, "max": 2024},
    "title_contains": "retrieval",
    "source": "openalex"
  }
}
```

## 9) Domain Keyword Gate (Anti‑Irrelevance)
Configured in `src/config.py`:
- `ENABLE_DOMAIN_KEYWORD_GATE`
- `DOMAIN_KEYWORD_MIN_OVERLAP`
- `DOMAIN_KEYWORDS`

Purpose: prevent unrelated sentences (e.g., “ChatGPT in education”) from being selected for RAG‑focused questions.

## 10) Tests
- `tests/test_evidence.py`
- `tests/test_verification.py`
- `tests/test_trace.py`

Run tests:
- `uv run python -m pytest tests/ -v`

## 11) Common Issues
- **ModuleNotFoundError: src** → run uvicorn from `rag-backend/`
- **MongoDB DNS / auth errors** → verify Atlas cluster is active, whitelist IP, correct password
- **No papers found** → broaden query or check OpenAlex status
- **FAISS index missing** → run `build-index` or use `--dynamic` mode

## 12) Known Enhancements Added Recently
- Metadata enrichment in chunks (title, category, tags, summary)
- Metadata filters in API + CLI + UI
- Domain keyword gate to block off‑topic results
- Sub‑question evidence re‑scoring

## 13) Handover Notes
- Re‑chunk and rebuild index after metadata changes so filters apply to existing data.
- Keep `.env` secrets private; rotate keys before production.
- For local LLM: set `LLM_PROVIDER=local` and ensure Ollama is running.
