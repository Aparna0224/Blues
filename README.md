# Blues — XAI-Enhanced Agentic RAG Research Assistant

A **six-stage Retrieval-Augmented Generation** system for trustworthy academic literature review. Given a research question, the system automatically decomposes it into sub-questions, fetches open-access papers, generates evidence-backed answers with sentence-level citations, verifies reliability with deterministic metrics, produces a narrative summary, and serves everything through a professional React dashboard.

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![React 19](https://img.shields.io/badge/React-19-61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![75 Tests](https://img.shields.io/badge/Tests-75%20passing-brightgreen)
![License MIT](https://img.shields.io/badge/License-MIT-yellow)

---

## Pipeline Overview

```
User Question
      │
      ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Stage 1  │────▶│ Stage 2  │────▶│ Stage 3  │────▶│ Stage 4  │────▶│ Stage 5  │────▶│ Stage 6  │
│ Planning │     │Retrieval │     │ Answer   │     │Verificat.│     │ Trace +  │     │ API + UI │
│  (LLM)   │     │(Dynamic) │     │  Gen     │     │  Agent   │     │ Summary  │     │(React)   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
```

| Stage | Name | Description |
|-------|------|-------------|
| **1** | Planning | LLM decomposes query into 2–4 sub-questions + search queries |
| **2** | Retrieval | OpenAlex → abstract filter → full-text PDF → chunk → SciBERT embed → FAISS search |
| **3** | Answer Generation | Assigns chunks to sub-questions, extracts sentence-level evidence, grouped output |
| **4** | Verification | Deterministic confidence scoring — similarity, diversity, density, conflict detection |
| **5** | Trace & Summary | Full execution trace + LLM narrative summary (100–200 words) |
| **6** | API & UI | FastAPI REST endpoints + React/TypeScript dashboard |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   rag-frontend (React 19)                       │
│          TypeScript · Vite · Tailwind CSS v4 · axios            │
│                   http://localhost:5173                          │
└────────────────────────────┬────────────────────────────────────┘
                             │  /api/* proxy
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  rag-backend (FastAPI)                           │
│             Python 3.11 · uvicorn · uv                          │
│                   http://localhost:8000                          │
│                                                                 │
│   Stages 1–3         Stage 4           Stage 5                  │
│  ┌───────────┐   ┌─────────────┐   ┌────────────┐              │
│  │ Planner   │   │ Verification│   │ Tracer +   │              │
│  │ Retriever │   │   Agent     │   │ Summarizer │              │
│  │ Generator │   │(deterministic)  │  (LLM)     │              │
│  └─────┬─────┘   └─────────────┘   └────────────┘              │
│        │                                                        │
│   ┌────┴──────────────────────────────┐                         │
│   ▼           ▼            ▼          ▼                         │
│ OpenAlex   SciBERT      FAISS    MongoDB Atlas                  │
│   API      (768d)    (IndexFlatIP)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript 5.9, Vite 7.3, Tailwind CSS v4, Lucide icons, axios |
| **API** | FastAPI 0.115, Uvicorn, Pydantic |
| **Backend** | Python 3.11+, uv package manager |
| **Database** | MongoDB Atlas |
| **Vector Store** | FAISS (`IndexFlatIP`, cosine similarity) |
| **Embeddings** | SciBERT (`allenai/scibert_scivocab_uncased`, 768d) |
| **LLM** | Groq Cloud / Google Gemini / Ollama (local) |
| **Paper Sources** | OpenAlex, Semantic Scholar, Unpaywall, NCBI E-utilities |
| **PDF Extraction** | PyMuPDF, BeautifulSoup4 |
| **Testing** | pytest — 75 tests (evidence, verification, trace) |

---

## Quick Start

### Prerequisites

- Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 18+, npm
- MongoDB Atlas account (free tier)
- Groq API key (free) — [console.groq.com/keys](https://console.groq.com/keys)

### 1. Clone

```bash
git clone https://github.com/Aparna0224/Blues.git
cd Blues
```

### 2. Backend

```bash
cd rag-backend
uv venv && .\.venv\Scripts\Activate.ps1   # Windows
uv pip sync pyproject.toml
cp .env.example .env                       # Edit with your credentials
python -c "import nltk; nltk.download('punkt_tab')"
```

### 3. Frontend

```bash
cd ../rag-frontend
npm install
```

### 4. Run

**Terminal 1 — Backend:**
```bash
cd rag-backend
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd rag-frontend
npm run dev
```

Open **http://localhost:5173**

> See [`rag-backend/README.md`](rag-backend/README.md) for CLI usage, environment variables, and backend details.
> See [`rag-frontend/README.md`](rag-frontend/README.md) for component reference and frontend configuration.

---

## Project Structure

```
Blues/
├── README.md                       ← Project overview (this file)
├── rag-backend.code-workspace
│
├── rag-backend/                    ← Python backend — Stages 1–6
│   ├── README.md                   ← Backend documentation
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   ├── api.py                  ← FastAPI REST API
│   │   ├── main.py                 ← CLI entry point
│   │   ├── config.py               ← Environment config
│   │   ├── database.py             ← MongoDB client
│   │   ├── vector_store.py         ← FAISS operations
│   │   ├── agents/                 ← PlannerAgent, VerificationAgent
│   │   ├── chunking/               ← TextChunker
│   │   ├── embeddings/             ← SciBERT embedder
│   │   ├── evidence/               ← Sentence-level extractor
│   │   ├── generation/             ← AnswerGenerator, Summarizer
│   │   ├── ingestion/              ← OpenAlex loader, full-text fetcher
│   │   ├── llm/                    ← Ollama, Gemini, Groq adapters
│   │   ├── retrieval/              ← Static + dynamic retrievers
│   │   └── trace/                  ← ExecutionTracer
│   ├── tests/                      ← 75 unit tests
│   ├── data/                       ← FAISS index
│   └── output/                     ← Pipeline output JSON
│
└── rag-frontend/                   ← React dashboard — Stage 6 UI
    ├── README.md                   ← Frontend documentation
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── components/             ← 8 UI components
        ├── services/api.ts         ← Axios client
        └── types/index.ts          ← TypeScript interfaces
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query` | Run the full RAG pipeline |
| `POST` | `/api/upload` | Upload a PDF for ingestion + indexing |
| `GET` | `/api/status` | System health + stats |
| `GET` | `/api/traces/{id}` | Retrieve execution trace |

Swagger docs: **http://localhost:8000/docs**

---

## Running Tests

```bash
cd rag-backend
uv run python -m pytest tests/ -v    # 75 tests
```

---

## License

MIT
