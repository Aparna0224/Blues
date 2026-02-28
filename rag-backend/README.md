# RAG Backend — XAI-Enhanced Agentic Research Assistant

A **Retrieval-Augmented Generation** system for semantic search over academic papers with sentence-level evidence extraction and agentic query decomposition.

Given a research question, the system automatically:
1. Decomposes it into sub-questions using an LLM
2. Fetches relevant open-access papers from OpenAlex / Semantic Scholar
3. Downloads and extracts full-text PDFs
4. Chunks, embeds, and retrieves the most relevant passages
5. Returns grouped answers with sentence-level evidence and citations

---

## Features

### Stage 1 — Core RAG Pipeline
- **Dual API Ingestion** — Fetch papers from OpenAlex and Semantic Scholar
- **SciBERT Embeddings** — 768-dimensional scientific text embeddings (`allenai/scibert_scivocab_uncased`)
- **FAISS Vector Search** — Fast similarity search with `IndexFlatIP`
- **MongoDB Storage** — Persistent paper and chunk storage on MongoDB Atlas
- **Answer Generation** — Structured answers with paper citations

### Stage 2 — Sentence-Level Evidence
- **Evidence Extraction** — Find the single most relevant sentence per chunk
- **Dual Scoring** — Chunk similarity + sentence-level evidence similarity
- **NLTK Tokenization** — Robust sentence splitting

### Stage 3 — Agentic RAG
- **LLM Abstraction** — Supports Ollama (local), Google Gemini, and Groq Cloud
- **PlannerAgent** — Decomposes complex queries into 2-4 sub-questions + search queries
- **Dynamic Paper Fetching** — Fetch fresh papers at query time via `--dynamic` flag
- **Two-Stage Retrieval** — Abstract relevance filtering → full-text download → chunk → retrieve
- **Full-Text Extraction** — PDF extraction via PyMuPDF, HTML via BeautifulSoup
- **Unpaywall + PMC Fallbacks** — Unpaywall API for OA links, NCBI E-utilities for PMC XML
- **Open-Access Filter** — Only fetches OA papers with downloadable URLs
- **Smart Chunk Assignment** — Embedding-based assignment with multi-assign + backfill guarantee
- **Grouped Output** — Answers organized by sub-question with claims, evidence, and sources

---

## Architecture

```
User Query
    │
    ▼
┌──────────────────┐
│   PlannerAgent   │  ← LLM decomposes query into sub-questions + search queries
│   (Groq/Gemini)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  DynamicRetriever│────►│   OpenAlex API   │
│   (Two-Stage)    │     │ Semantic Scholar │
└────────┬─────────┘     └──────────────────┘
         │
    Stage A: Embed abstracts → cosine similarity filter
    Stage B: Download full-text PDF → chunk → embed → retrieve
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  Full-Text       │────►│  PyMuPDF (PDF)   │
│  Fetcher         │     │  BeautifulSoup   │
│                  │     │  Unpaywall API   │
│                  │     │  NCBI E-utils    │
└────────┬─────────┘     └──────────────────┘
         │
         ▼
┌──────────────────┐
│  TextChunker     │  ← 8–12 sentence chunks
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  EmbeddingGen    │────►│  FAISS Index     │
│  (SciBERT 768d)  │     │  (IndexFlatIP)   │
└────────┬─────────┘     └──────────────────┘
         │
         ▼
┌──────────────────┐
│  Evidence        │  ← Sentence-level evidence extraction
│  Extractor       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  AnswerGenerator │  ← Grouped output by sub-question with citations
└──────────────────┘
```

---

## Prerequisites

- **Python 3.11+**
- **uv** — Fast Python package manager ([install guide](https://docs.astral.sh/uv/getting-started/installation/))
- **MongoDB Atlas** account — Free tier works ([mongodb.com/atlas](https://www.mongodb.com/atlas))
- **Groq API key** (recommended, free) — [console.groq.com/keys](https://console.groq.com/keys)
- **OpenAlex API key** (optional, free) — [openalex.org/settings/api](https://openalex.org/settings/api)

---

## Setup

### 1. Clone and navigate

```bash
git clone https://github.com/Aparna0224/Blues.git
cd Blues/rag-backend
```

### 2. Create virtual environment

```bash
uv venv
```

### 3. Activate environment

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
uv pip sync pyproject.toml
```

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGO_DB=xai_rag

# LLM (pick one provider)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# Optional (improves paper fetching rate limits)
OPENALEX_API_KEY=your_key_here
```

### 6. Download NLTK data (first time only)

```bash
python -c "import nltk; nltk.download('punkt_tab')"
```

---

## Usage

### Quick Start — Full Agentic RAG (Recommended)

Run a research question with dynamic paper fetching and agentic planning:

```bash
uv run python -m src.main query \
  --query "What are the main approaches to explainable AI in medical diagnosis?" \
  --plan --dynamic
```

This will:
1. Decompose the query into sub-questions (via LLM)
2. Fetch fresh open-access papers from OpenAlex
3. Download full-text PDFs where available
4. Chunk and embed all content
5. Retrieve the most relevant chunks
6. Display grouped answer organized by sub-question

Output is saved to `rag_output.txt`.

### CLI Commands

#### Ingest papers into the database

```bash
# From OpenAlex (default, OA-only)
uv run python -m src.main ingest --query "machine learning" --max-results 10

# From Semantic Scholar
uv run python -m src.main ingest --query "deep learning" --source semantic_scholar

# From both APIs
uv run python -m src.main ingest --query "neural networks" --source both --max-results 20
```

#### Build FAISS index (for static retrieval)

```bash
uv run python -m src.main build-index
```

#### Query the system

```bash
# Stage 1: Basic chunk retrieval (requires pre-ingested data + FAISS index)
uv run python -m src.main query --query "What is deep learning?" --top-k 5

# Stage 2: With sentence-level evidence
uv run python -m src.main query --query "What is deep learning?" --evidence

# Stage 3: Agentic RAG with static index
uv run python -m src.main query --query "What is deep learning?" --plan

# Stage 3: Agentic RAG with dynamic paper fetching (no pre-ingestion needed)
uv run python -m src.main query --query "What is deep learning?" --plan --dynamic
```

#### Check system status

```bash
uv run python -m src.main status
```

#### Reset all data

```bash
uv run python -m src.main reset
```

---

## Query Modes Explained

| Flag | Mode | What it does | Pre-ingestion needed? |
|------|------|--------------|-----------------------|
| _(none)_ | Stage 1 | FAISS search → chunk retrieval → answer | Yes |
| `--evidence` | Stage 2 | + sentence-level evidence extraction | Yes |
| `--plan` | Stage 3 (static) | + LLM query decomposition → multi-retrieve | Yes |
| `--plan --dynamic` | Stage 3 (dynamic) | + fetch fresh papers on-the-fly from APIs | **No** |

---

## Project Structure

```
rag-backend/
├── src/
│   ├── __init__.py
│   ├── config.py                   # Configuration from .env
│   ├── database.py                 # MongoDB connection (singleton)
│   ├── main.py                     # CLI entry point (Click)
│   ├── vector_store.py             # FAISS index operations
│   │
│   ├── agents/
│   │   └── planner.py              # PlannerAgent — query decomposition via LLM
│   │
│   ├── chunking/
│   │   └── processor.py            # TextChunker — 8-12 sentence chunks
│   │
│   ├── embeddings/
│   │   └── embedder.py             # EmbeddingGenerator — SciBERT (768d)
│   │
│   ├── evidence/
│   │   └── extractor.py            # EvidenceExtractor — sentence-level scoring
│   │
│   ├── generation/
│   │   └── generator.py            # AnswerGenerator — grouped output with citations
│   │
│   ├── ingestion/
│   │   ├── loader.py               # PaperIngestor — OpenAlex + Semantic Scholar
│   │   └── fulltext.py             # FullTextFetcher — PDF/HTML/Unpaywall/PMC
│   │
│   ├── llm/
│   │   ├── base.py                 # BaseLLM abstract class
│   │   ├── factory.py              # get_llm() factory
│   │   ├── local.py                # Ollama (local)
│   │   ├── gemini_llm.py           # Google Gemini API
│   │   └── groq_llm.py             # Groq Cloud API (recommended)
│   │
│   └── retrieval/
│       ├── retriever.py            # Retriever — FAISS-based static search
│       └── dynamic_retriever.py    # DynamicRetriever — two-stage live retrieval
│
├── tests/
│   └── test_evidence.py            # 21 unit tests for evidence extraction
│
├── data/
│   └── faiss_index.bin             # FAISS index file (generated)
│
├── output/                         # Cached pipeline outputs (JSON)
├── pyproject.toml                  # Dependencies (uv)
├── .env.example                    # Environment variable template
└── rag_output.txt                  # Latest query output
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGO_URI` | **Yes** | — | MongoDB Atlas connection string |
| `MONGO_DB` | No | `xai_rag` | Database name |
| `LLM_PROVIDER` | No | `local` | LLM backend: `local`, `gemini`, or `groq` |
| `GROQ_API_KEY` | If groq | — | Groq Cloud API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model |
| `GEMINI_API_KEY` | If gemini | — | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model |
| `OLLAMA_BASE_URL` | If local | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3:8b-instruct` | Ollama model |
| `OPENALEX_API_KEY` | No | — | OpenAlex API key (higher rate limits) |
| `SEMANTIC_SCHOLAR_API_KEY` | No | — | Semantic Scholar API key |
| `EMBEDDING_MODEL` | No | `allenai/scibert_scivocab_uncased` | Embedding model |
| `FAISS_INDEX_PATH` | No | `./data/faiss_index.bin` | FAISS index file path |
| `TOP_K` | No | `5` | Default chunks to retrieve |
| `LLM_TEMPERATURE` | No | `0.1` | LLM generation temperature |
| `DEBUG` | No | `False` | Enable debug output |

---

## Running Tests

```bash
# Run all tests
uv run python -m pytest tests/ -v

# Run evidence extraction tests only
uv run python -m pytest tests/test_evidence.py -v
```

---

## How It Works (Dynamic Mode)

When you run with `--plan --dynamic`, the pipeline executes:

```
1. PLANNER AGENT
   User query → LLM → sub-questions + search queries

2. STAGE A — Abstract Relevance Filtering
   Search queries → OpenAlex API (OA-only) → fetch papers
   Embed each abstract → cosine similarity vs query
   Keep papers above threshold (0.35)

3. STAGE B — Full-Text Fetch & Retrieval
   For each relevant paper:
     Try: direct PDF URL → Unpaywall API → NCBI E-utilities (PMC)
     Extract text: PyMuPDF (PDF) or BeautifulSoup (HTML)
   Chunk full text into 8-12 sentence chunks
   Embed all chunks with SciBERT
   Cosine similarity search → top-k chunks

4. EVIDENCE EXTRACTION
   For each top chunk → find the single most relevant sentence

5. ANSWER GENERATION
   Assign chunks to sub-questions (embedding similarity)
   Display grouped output with claims, evidence scores, and sources
```

---

## Full-Text Download Strategy

The system tries multiple methods to get paper full text:

| Priority | Method | Success Rate |
|----------|--------|-------------|
| 1 | Direct PDF URL from OpenAlex `best_oa_location` | ~60% |
| 2 | Open access URL (`oa_url`) | ~10% |
| 3 | Publisher-specific alternatives (EuropePMC, etc.) | ~5% |
| 4 | **Unpaywall API** — finds working OA links via DOI | ~15% |
| 5 | **NCBI E-utilities** — fetches PMC full-text XML directly | ~10% |
| Fallback | Use abstract only | Always works |

> **Note:** Some publishers (e.g., MDPI) block all automated downloads. The system gracefully falls back to using the abstract for these papers.

---

## Troubleshooting

### MongoDB connection error
- Verify `MONGO_URI` in `.env` is correct
- Check that your IP is whitelisted in MongoDB Atlas → Network Access
- Try `0.0.0.0/0` (allow from anywhere) for testing

### "No papers found" during dynamic retrieval
- Check internet connectivity
- OpenAlex API may be temporarily down — try again in a minute
- Try a broader query

### LLM errors (planning step fails)
- If using Groq: verify `GROQ_API_KEY` in `.env`
- If using Ollama: ensure `ollama serve` is running and the model is pulled
- Check `LLM_PROVIDER` matches your setup

### Out of memory during embedding
- Reduce `--max-results` when ingesting
- The SciBERT model uses ~500MB RAM — 8GB system RAM recommended

### FAISS index not found (static mode)
- Run `uv run python -m src.main build-index` first
- Or use `--dynamic` mode which doesn't need a pre-built index

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Package Manager | uv |
| Database | MongoDB Atlas |
| Vector Store | FAISS (IndexFlatIP, inner product) |
| Embeddings | SciBERT (`allenai/scibert_scivocab_uncased`, 768d) |
| LLM | Groq Cloud / Google Gemini / Ollama |
| Paper APIs | OpenAlex, Semantic Scholar |
| Full-Text | PyMuPDF, BeautifulSoup, Unpaywall, NCBI E-utilities |
| CLI | Click |
| PDF Extraction | PyMuPDF (fitz) |
| HTML Extraction | BeautifulSoup4 |

---

## License

MIT
