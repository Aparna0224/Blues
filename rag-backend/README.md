# RAG Backend

Python backend for the Blues XAI-Enhanced Agentic RAG Research Assistant. Implements Stages 1�5 of the pipeline (planning, retrieval, answer generation, verification, trace & summary) plus the FastAPI REST API (Stage 6).

---

## Setup

### 1. Create virtual environment

```bash
cd rag-backend
uv venv
```

### 2. Activate

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
uv pip sync pyproject.toml
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGO_DB=xai_rag

# LLM Provider (pick one: local, gemini, groq)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Optional � higher rate limits for paper fetching
OPENALEX_API_KEY=your_key_here
```

### 5. Download NLTK data (first time only)

```bash
python -c "import nltk; nltk.download('punkt_tab')"
```

---

## Running the API Server

```bash
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

Swagger docs: **http://localhost:8000/docs**

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query` | Run the full RAG pipeline on a research question |
| `POST` | `/api/upload` | Upload a PDF paper for ingestion, chunking, and indexing |
| `GET` | `/api/status` | System health � MongoDB, FAISS vectors, LLM provider |
| `GET` | `/api/traces/{id}` | Retrieve a saved execution trace |

### POST /api/query � Request Body

```json
{
  "query": "What are the main approaches to explainable AI?",
  "num_documents": 15,
  "mode": "dynamic",
  "include_summary": true
}
```

### POST /api/query � Response

```json
{
  "execution_id": "055b1122-...",
  "status": "success",
  "planning": {
    "main_question": "...",
    "sub_questions": ["...", "..."],
    "search_queries": ["...", "..."],
    "latency_ms": 1234.5
  },
  "grouped_answer": "## Sub-question 1\n...",
  "chunks_used": 15,
  "papers_found": [
    { "paper_id": "...", "title": "...", "authors": "...", "year": "2023", "doi": "..." }
  ],
  "verification": {
    "confidence_score": 0.89,
    "metrics": {
      "avg_similarity": 0.72,
      "source_diversity": 6,
      "normalized_source_diversity": 0.85,
      "evidence_density": 0.93,
      "conflicts_detected": []
    },
    "warnings": [],
    "audit": {
      "total_claims_received": 15,
      "claims_after_dedup": 14,
      "claims_after_relevance_filter": 13,
      "claims_above_similarity_threshold": 12,
      "claims_used_for_scoring": 12,
      "claims_rejected": 3
    }
  },
  "summary": "According to recent studies...",
  "total_time_ms": 45000.0,
  "warnings": []
}
```

---

## CLI Usage

### Full Agentic RAG (Recommended)

```bash
uv run python -m src.main query \
  --query "What are the main approaches to explainable AI in medical diagnosis?" \
  --plan --dynamic
```

### All Commands

```bash
# Ingest papers into MongoDB
uv run python -m src.main ingest --query "machine learning" --max-results 10

# Build FAISS index (for static/cached mode)
uv run python -m src.main build-index

# Query � increasing capability
uv run python -m src.main query --query "..." --top-k 5              # Stage 1: basic retrieval
uv run python -m src.main query --query "..." --evidence              # Stage 2: + evidence
uv run python -m src.main query --query "..." --plan                  # Stage 3: + planning (static)
uv run python -m src.main query --query "..." --plan --dynamic        # Stage 3: + live fetch

# System status
uv run python -m src.main status

# Reset all data
uv run python -m src.main reset
```

### Query Modes

| Flag | Mode | Pre-ingestion? |
|------|------|---------------|
| _(none)_ | Basic FAISS retrieval | Yes |
| `--evidence` | + sentence-level evidence | Yes |
| `--plan` | + LLM query decomposition (static index) | Yes |
| `--plan --dynamic` | + live paper fetching from APIs | **No** |

---

## Pipeline Stages

### Stage 1 � Core RAG
- **Dual API Ingestion** � OpenAlex + Semantic Scholar
- **SciBERT Embeddings** � `allenai/scibert_scivocab_uncased` (768d)
- **FAISS Vector Search** � `IndexFlatIP` (inner product / cosine similarity)
- **MongoDB Atlas** � Persistent paper + chunk storage

### Stage 2 � Sentence-Level Evidence
- **EvidenceExtractor** � Finds the single most relevant sentence per chunk
- **Dual Scoring** � Chunk similarity + sentence evidence similarity
- **NLTK** � `punkt_tab` sentence tokenizer

### Stage 3 � Agentic RAG
- **PlannerAgent** � LLM decomposes query into 2�4 sub-questions + search queries
- **DynamicRetriever** � Two-stage: abstract relevance filter ? full-text fetch ? chunk ? retrieve
- **FullTextFetcher** � PDF (PyMuPDF), HTML (BeautifulSoup), Unpaywall, NCBI E-utilities
- **Open-Access Filter** � Only OA papers with downloadable URLs
- **Smart Chunk Assignment** � Embedding-based multi-assign with backfill guarantee
- **LLM Abstraction** � `BaseLLM` ? Ollama / Gemini / Groq via `get_llm()` factory

### Stage 4 � Verification Agent
- **Deterministic** � No LLM calls; pure metrics
- **Claim Relevance Filtering** � Rejects generic/motivational sentences
- **Claim Deduplication** � N-gram Jaccard overlap
- **Similarity Threshold Gating** � Ignores weak matches
- **Metrics** � `avg_similarity`, `source_diversity`, `evidence_density`
- **Cross-Paper Conflict Detection** � Flags contradictory findings
- **Structured Audit Log** � Full filtering pipeline transparency

### Stage 5 � Trace & Summary
- **ExecutionTracer** � Records every pipeline decision (JSON + MongoDB)
- **PipelineSummarizer** � LLM generates 100�200 word narrative summary

---

## Project Structure

```
rag-backend/
+-- pyproject.toml                      ? Dependencies (uv)
+-- .env.example                        ? Environment variable template
+-- rag_output.txt                      ? Latest CLI output
�
+-- src/
�   +-- __init__.py
�   +-- config.py                       ? Centralised config from .env
�   +-- database.py                     ? MongoDB client (singleton)
�   +-- main.py                         ? CLI entry point (Click)
�   +-- api.py                          ? FastAPI REST API (Stage 6)
�   +-- vector_store.py                 ? FAISS index operations
�   �
�   +-- agents/
�   �   +-- planner.py                  ? PlannerAgent � query decomposition
�   �   +-- verification.py             ? VerificationAgent � confidence scoring
�   �
�   +-- chunking/
�   �   +-- processor.py                ? TextChunker � 8�12 sentence chunks
�   �
�   +-- embeddings/
�   �   +-- embedder.py                 ? EmbeddingGenerator � SciBERT (768d)
�   �
�   +-- evidence/
�   �   +-- extractor.py                ? EvidenceExtractor � sentence-level scoring
�   �
�   +-- generation/
�   �   +-- generator.py                ? AnswerGenerator � grouped output with citations
�   �   +-- summarizer.py               ? PipelineSummarizer � LLM narrative summary
�   �
�   +-- ingestion/
�   �   +-- loader.py                   ? PaperIngestor � OpenAlex + Semantic Scholar
�   �   +-- fulltext.py                 ? FullTextFetcher � PDF/HTML/Unpaywall/PMC
�   �
�   +-- llm/
�   �   +-- base.py                     ? BaseLLM abstract class
�   �   +-- factory.py                  ? get_llm() factory
�   �   +-- local.py                    ? Ollama adapter
�   �   +-- gemini_llm.py               ? Google Gemini adapter
�   �   +-- groq_llm.py                 ? Groq Cloud adapter
�   �
�   +-- retrieval/
�   �   +-- retriever.py                ? Retriever � static FAISS search
�   �   +-- dynamic_retriever.py        ? DynamicRetriever � two-stage live retrieval
�   �
�   +-- trace/
�       +-- tracer.py                   ? ExecutionTracer � pipeline trace
�
+-- tests/
�   +-- test_evidence.py                ? 21 tests � evidence extraction
�   +-- test_verification.py            ? 33 tests � verification agent
�   +-- test_trace.py                   ? 21 tests � execution tracer
�
+-- data/
�   +-- faiss_index.bin                 ? FAISS index (generated)
�
+-- output/                             ? Pipeline outputs (JSON)
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGO_URI` | **Yes** | � | MongoDB Atlas connection string |
| `MONGO_DB` | No | `xai_rag` | Database name |
| `LLM_PROVIDER` | No | `local` | `local` / `gemini` / `groq` |
| `GROQ_API_KEY` | If groq | � | Groq Cloud API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `GEMINI_API_KEY` | If gemini | � | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name |
| `OLLAMA_BASE_URL` | If local | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3:8b-instruct` | Ollama model name |
| `OPENALEX_API_KEY` | No | � | OpenAlex polite pool key |
| `SEMANTIC_SCHOLAR_API_KEY` | No | � | Semantic Scholar API key |
| `EMBEDDING_MODEL` | No | `allenai/scibert_scivocab_uncased` | HuggingFace embedding model |
| `FAISS_INDEX_PATH` | No | `./data/faiss_index.bin` | FAISS index file path |
| `TOP_K` | No | `5` | Default chunks to retrieve |
| `LLM_TEMPERATURE` | No | `0.1` | LLM generation temperature |
| `DEBUG` | No | `False` | Enable debug output |

---

## Tests

```bash
# All 75 tests
uv run python -m pytest tests/ -v

# By module
uv run python -m pytest tests/test_evidence.py -v        # 21 � evidence extraction
uv run python -m pytest tests/test_verification.py -v     # 33 � verification agent
uv run python -m pytest tests/test_trace.py -v            # 21 � execution tracer

# With coverage
uv run python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## Dynamic Mode Pipeline

```
1. PLANNING
   User query ? LLM ? sub-questions + search queries

2. ABSTRACT FILTERING
   Search queries ? OpenAlex API (OA-only)
   Embed abstracts ? cosine similarity filter (threshold 0.35)

3. FULL-TEXT RETRIEVAL
   For each relevant paper:
     ? Direct PDF URL (OpenAlex best_oa_location)
     ? Unpaywall API (OA link via DOI)
     ? NCBI E-utilities (PMC XML)
     ? Fallback: abstract only
   Extract text: PyMuPDF (PDF) / BeautifulSoup (HTML/XML)

4. CHUNKING + EMBEDDING
   8�12 sentence chunks ? SciBERT (768d) ? FAISS search

5. EVIDENCE EXTRACTION
   Per chunk ? most relevant sentence
   Assign chunks to sub-questions via embedding similarity

6. ANSWER GENERATION
   Grouped output by sub-question with claims + citations

7. VERIFICATION
   Claim filtering ? dedup ? relevance ? similarity threshold
   Metrics + conflict detection + audit log

8. SUMMARY
   LLM narrative summary (100�200 words)
   Full execution trace saved to JSON + MongoDB
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MongoDB connection error | Verify `MONGO_URI`; whitelist IP in Atlas Network Access |
| "No papers found" | Check internet; try broader query; OpenAlex may be down |
| LLM planning fails | Check `LLM_PROVIDER` + API key in `.env` |
| `ModuleNotFoundError: No module named 'src'` | Run uvicorn from `rag-backend/` directory |
| Out of memory | Reduce `--max-results`; SciBERT needs ~500 MB RAM |
| FAISS index not found | Run `build-index` or use `--dynamic` mode |
