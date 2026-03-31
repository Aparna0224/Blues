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
Blues/
├── rag-backend/            # Python FastAPI + CLI + RAG pipeline
│   ├── src/
│   │   ├── agents/         # Planner + Verification agents
│   │   ├── chunking/       # Text chunking with metadata enrichment
│   │   ├── embeddings/     # SciBERT embedding generation (singleton)
│   │   ├── evidence/       # Sentence-level evidence extraction
│   │   ├── generation/     # Answer generation + LLM summarizer
│   │   ├── ingestion/      # Paper fetching (OpenAlex/Semantic Scholar) + full-text
│   │   ├── llm/            # LLM abstraction (Local/Gemini/Groq)
│   │   ├── retrieval/      # Static FAISS + Dynamic retriever
│   │   ├── trace/          # Execution trace recording
│   │   ├── api.py          # FastAPI REST endpoints
│   │   ├── config.py       # Centralized configuration
│   │   ├── database.py     # MongoDB connection (singleton)
│   │   ├── main.py         # CLI entry point
│   │   └── vector_store.py # FAISS index management (singleton)
│   ├── tests/
│   │   ├── test_evidence.py
│   │   ├── test_generator.py
│   │   ├── test_trace.py
│   │   └── test_verification.py
│   ├── pyproject.toml
│   └── .env
└── rag-frontend/           # React + TypeScript + Vite UI
    └── src/
        ├── components/     # UI components
        ├── services/       # API client
        ├── types/          # TypeScript type definitions
        ├── App.tsx
        └── main.tsx
```

## 3) Architecture — Pipeline Stages

### Stage 1 — Ingestion & Indexing
- **Paper Fetching**: `src/ingestion/loader.py` — OpenAlex + Semantic Scholar APIs
- **Full-Text**: `src/ingestion/fulltext.py` — PDF (PyMuPDF), HTML (BeautifulSoup), Unpaywall, PMC
- **Chunking**: `src/chunking/processor.py` — NLTK sentence-level chunking (8–12 sentences per chunk)
- **Metadata Enrichment**: Each chunk gets: title, year, section, summary, tags, category, source
- **Embeddings**: `src/embeddings/embedder.py` — SciBERT (`allenai/scibert_scivocab_uncased`, 768d), singleton pattern
- **Vector Store**: `src/vector_store.py` — FAISS IndexFlatIP (cosine similarity via inner product), singleton

### Stage 2 — Evidence Extraction
- **Module**: `src/evidence/extractor.py`
- Splits chunk text into sentences (NLTK `sent_tokenize`)
- Embeds sentences with SciBERT, computes cosine similarity against query
- Selects best-matching sentence per chunk with evidence score
- Filters: junk sentence detection (citations, headers, numeric noise, short sentences, prompt artifacts)
- Keyword overlap validation against query terms
- Configurable thresholds: `EVIDENCE_MIN_SIMILARITY`, `EVIDENCE_KEYWORD_MIN_OVERLAP`

### Stage 3 — Planner Agent + Retrieval
- **Planner**: `src/agents/planner.py`
  - Uses LLM to decompose user query into 2–4 sub-questions + 2–4 search queries
  - JSON output parsing with fallback handling
  - Fallback plan generation when LLM fails
- **Static Retriever**: `src/retrieval/retriever.py`
  - FAISS search over pre-indexed chunks
  - 3-layer filtering: similarity threshold → domain keyword gate → keyword overlap
  - Multi-query retrieval with deduplication by chunk_id
  - Evidence extraction integration
- **Dynamic Retriever**: `src/retrieval/dynamic_retriever.py`
  - Two-stage live retrieval:
    - **Stage A**: Fetch papers from APIs → embed abstracts → filter by relevance threshold
    - **Stage B**: Fetch full text → chunk → embed → cosine similarity search
  - Caches embeddings in MongoDB for reuse
  - Reuses existing DB chunks when available

### Stage 4 — Answer Generation + Verification
- **Answer Generator**: `src/generation/generator.py`
  - Assigns chunks to sub-questions using embedding similarity matrix
  - Primary assignment (exclusive) + selective multi-assignment + backfill guarantee
  - Re-scores evidence against each sub-question
  - Generates grouped answer with claims, evidence scores, source metadata
- **Verification Agent**: `src/agents/verification.py`
  - Deterministic (no LLM calls) confidence scoring
  - Pipeline: deduplication → relevance filtering → similarity threshold gating → metrics
  - Metrics: avg similarity, source diversity, evidence density, conflict detection
  - Full audit log of filtering pipeline

### Stage 5 — Trace + Summary
- **Execution Tracer**: `src/trace/tracer.py`
  - Records every pipeline decision as JSON
  - Stores: planning, retrieval, filtering, evidence selection, verification stages
  - Saved to MongoDB (`execution_traces` collection) and `output/` directory
- **Pipeline Summarizer**: `src/generation/summarizer.py`
  - LLM-generated 100–200 word narrative summary
  - Conversational, publication-grade style with natural citations
  - Confidence footer from verification results

### Stage 6 — REST API + UI
- **API Server**: `src/api.py` (FastAPI)
- **Frontend**: React + TypeScript + Vite

## 4) Backend Setup (rag-backend)

### Requirements
- Python 3.11+
- uv package manager
- MongoDB Atlas connection

### Dependencies (pyproject.toml)
```
Core:       requests, python-dotenv, click
NLP:        nltk, sentence-transformers, numpy
Vector:     faiss-cpu
Database:   pymongo
Full-text:  pymupdf, beautifulsoup4
API:        fastapi, uvicorn, python-multipart
Dev:        pytest, pytest-cov
```

### Install & Run
1. Create and activate env
   - `uv venv`
   - `source .venv/bin/activate`

2. Install deps
   - `uv pip sync pyproject.toml`

3. Configure `.env`
   - `MONGO_URI` (Atlas URI with real password)
   - `LLM_PROVIDER` (local | groq | gemini)
   - API keys (Groq/Gemini/OpenAlex/Semantic Scholar)

4. Run API server
   - `uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload`

### CLI Commands
```bash
# Ingest papers
uv run python -m src.main ingest --query "machine learning" --max-results 10

# Build FAISS index
uv run python -m src.main build-index

# Basic query
uv run python -m src.main query --query "..." --top-k 5

# Query with evidence
uv run python -m src.main query --query "..." --evidence

# Agentic query (static retrieval)
uv run python -m src.main query --query "..." --plan

# Agentic query (dynamic retrieval)
uv run python -m src.main query --query "..." --plan --dynamic
```

### CLI Metadata Filters
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
```bash
npm install
npm run dev
```

Frontend is served at `http://localhost:5173` and proxies `/api` to `http://localhost:8000`.

### Components
| Component | File | Purpose |
|---|---|---|
| QueryForm | `QueryForm.tsx` | Research question input + mode/filter controls |
| ResultsPanel | `ResultsPanel.tsx` | Grouped answer with claims & evidence |
| VerificationCard | `VerificationCard.tsx` | Verification metrics display |
| SummaryPanel | `SummaryPanel.tsx` | LLM-generated research summary |
| PapersTable | `PapersTable.tsx` | Source papers table |
| FileUpload | `FileUpload.tsx` | PDF upload for ingestion |
| StatusBar | `StatusBar.tsx` | System status (MongoDB/FAISS/LLM) |
| LoadingSpinner | `LoadingSpinner.tsx` | Loading indicator |

## 6) API Surface (FastAPI)

### POST /api/query
Request body:
```json
{
  "query": "string",
  "num_documents": 15,
  "mode": "dynamic | cached",
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

Response: `QueryResponse` with execution_id, planning, grouped_answer, chunks_used, papers_found, verification, summary, total_time_ms, warnings.

### POST /api/upload
Upload a PDF paper for ingestion → chunk → embed → FAISS index.

### GET /api/status
Returns: mongodb status, papers_count, chunks_count, faiss_vectors, llm_provider, llm_model.

### GET /api/traces/{execution_id}
Retrieve a saved execution trace JSON.

## 7) LLM Configuration

| Provider | Config Key | Model |
|---|---|---|
| Local (Ollama) | `LLM_PROVIDER=local` | `OLLAMA_MODEL` (default: `llama3:8b-instruct`) |
| Google Gemini | `LLM_PROVIDER=gemini` | `GEMINI_MODEL` (default: `gemini-2.0-flash`) |
| Groq Cloud | `LLM_PROVIDER=groq` | `GROQ_MODEL` (default: `llama-3.3-70b-versatile`) |

LLM is used only for: query decomposition (planner) and summary generation. All verification is deterministic (no LLM).

## 8) Retrieval Configuration (config.py)

| Setting | Default | Purpose |
|---|---|---|
| `RETRIEVAL_MIN_SIMILARITY` | 0.45 | Minimum cosine similarity to keep a chunk |
| `EVIDENCE_MIN_SIMILARITY` | 0.50 | Minimum similarity for sentence-level evidence |
| `KEYWORD_MIN_OVERLAP` | 2 | Required keyword overlap between query and chunk |
| `EVIDENCE_KEYWORD_MIN_OVERLAP` | 1 | Keyword overlap for evidence sentences |
| `SUBQUESTION_ASSIGN_THRESHOLD` | 0.40 | Min similarity to assign chunk to sub-question |
| `DYNAMIC_ABSTRACT_MIN_SIMILARITY` | 0.45 | Abstract relevance threshold (dynamic mode) |
| `MIN_UNIQUE_PAPERS_FOR_CLAIMS` | 2 | Minimum papers needed for claim generation |
| `ENABLE_DOMAIN_KEYWORD_GATE` | True | Enable domain keyword filtering |
| `DOMAIN_KEYWORD_MIN_OVERLAP` | 1 | Required domain keyword overlap |
| `FILTER_QUESTION_SENTENCES` | True | Filter out question-ending sentences |
| `TOP_K` | 5 | Default number of chunks to retrieve |
| `MIN_CHUNK_SENTENCES` | 8 | Minimum sentences per chunk |
| `MAX_CHUNK_SENTENCES` | 12 | Maximum sentences per chunk |

### Domain Keywords
Default: `rag, retrieval, augmentation, context, grounding, assistant, research, query, documents`

## 9) MongoDB Collections

| Collection | Key Fields | Indexes |
|---|---|---|
| `papers` | paper_id, title, abstract, full_text, authors, year, doi, source | paper_id (unique) |
| `chunks` | chunk_id, paper_id, text, section, embedding_index, metadata, embedding | chunk_id (unique), paper_id |
| `execution_traces` | execution_id, timestamp, status, stages | execution_id (unique), timestamp, status |

## 10) Singleton Pattern Summary

Three heavy resources use singleton pattern to avoid reinitialization:
1. **EmbeddingGenerator** (`embedder.py`) — SciBERT model loaded once
2. **FAISSVectorStore** (`vector_store.py`) — FAISS index loaded once
3. **MongoDBClient** (`database.py`) — MongoDB connection reused

## 11) Tests

```bash
uv run python -m pytest tests/ -v
```

| Test File | Coverage |
|---|---|
| `test_evidence.py` | Sentence splitting, similarity, evidence extraction, junk filtering |
| `test_generator.py` | Grouped answer formatting, claim snippet generation |
| `test_trace.py` | Execution trace recording and serialization |
| `test_verification.py` | Deduplication, filtering, confidence scoring, conflict detection |

## 12) Known Issues & Limitations

- **Sub-question evidence gaps**: Pure semantic retrieval (FAISS/SciBERT) can miss keyword-relevant chunks. Sub-questions using different vocabulary than papers may return no evidence. **Planned fix**: Hybrid BM25 + Semantic + RRF retrieval.
- **Domain keyword gate**: Currently tuned for RAG-focused queries. Queries on other topics (e.g., "AGI") may have evidence filtered by the domain gate.
- **Config duplicate overrides**: Lines 38–43 of `config.py` contain hardcoded values that override env-var-based settings above them.
- **ModuleNotFoundError: src** → must run uvicorn from `rag-backend/` directory.
- **MongoDB DNS / auth errors** → verify Atlas cluster is active, whitelist IP, correct password.
- **No papers found** → broaden query or check OpenAlex status.
- **FAISS index missing** → run `build-index` or use `--dynamic` mode.

## 13) Recent Enhancements
- Metadata enrichment in chunks (title, category, tags, summary)
- Metadata filters in API + CLI + UI
- Domain keyword gate to block off-topic results
- Sub-question evidence re-scoring in grouped answer generation
- Embedding caching in MongoDB (dynamic retriever reuses stored embeddings)
- Junk sentence filtering (citations, headers, numeric noise, prompt artifacts)
- Singleton pattern for SciBERT model, FAISS index, and MongoDB connection
- Pipeline summarizer with LLM-generated narrative summaries
- Full execution tracing (JSON) with MongoDB storage
- Multi-query retrieval with chunk deduplication

## 14) Handover Notes
- Re-chunk and rebuild index after metadata changes so filters apply to existing data.
- Keep `.env` secrets private; rotate keys before production.
- For local LLM: set `LLM_PROVIDER=local` and ensure Ollama is running.
- The dynamic retriever is the recommended mode — it fetches fresh papers and doesn't require a pre-built FAISS index.
