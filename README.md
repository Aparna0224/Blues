# Blues RAG — Agentic Research Assistant

Blues is an explainable, agentic RAG (Retrieval-Augmented Generation) pipeline tailored for scientific literature and research synthesis. Unlike standard chat-based RAGs, Blues focuses on **traceable evidence**, **conflict detection**, and **professional structured summaries**.

## 🌟 Key Features

### 🧠 Agentic Backend Pipeline
- **Query Planner:** Breaks complex user requests into smaller sub-questions for thorough processing.
- **Hybrid Retrieval (BM25 + Semantic):** Uses Reciprocal Rank Fusion to ensure both exact keyword matching and semantic concept alignment.
- **Sentence-Level Extraction:** Isolates exact sentence boundaries for precision citations rather than returning walls of generic text.
- **XAI Conflict Detection:** Cross-compares papers to actively flag theoretical or empirical disagreements.
- **Structured Validation:** Automatically grounds generated insights with `Traceable Citations` and confidence metrics.

### 💻 Professional User Interface
- **Dark-Theme Dashboard:** Clean, professional interface styled with Lucide react icons and readable standard web-safe fonts.
- **Project Library:** Persists structured project histories, saved syntheses, and analysis queries directly to local storage workspaces.
- **XAI Trace Inspector:** Dedicated panels to analyze the reasoning steps of the LLM pipeline.
- **Conflict Map:** Highlights contradictory claims between papers with clear explanations.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (using `uv`)
- Node.js 18+
- Active API endpoint for LLM completion (if configured outside testing modes)

### Backend Setup
```bash
cd rag-backend
uv pip install -r requirements.txt
# Ensure environment variables are loaded
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd rag-frontend
npm install
npm run dev
```

## 🏗 System Architecture

The pipeline follows a strict execution flow:
1. `Planning` → Decomposes query.
2. `Retrieval` → Hybrid fetches candidate data from SciBERT embeddings + BM25 local index.
3. `Evidence Extraction` → Filters and extracts precision sentences.
4. `Drafting & Verification` → Drafts intermediate insights, performs validation.
5. `Final Summary` → Produces a formatted comparison summary across topics, methodology, and synthesis.

## 🤝 Project Handoff
Refer to `HANDOVER.md` for in-depth technical configuration, testing standards, and module capabilities. See `CODE_CHANGES_SUMMARY.md` for recent architectural evolution.
