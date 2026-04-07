# Blues — Full Project Handover (Backend + Frontend)

Prepared for: External product/content review (Feedough)
Project: **Blues**
Type: **Agentic RAG Research Assistant**

---

## 1) Product Overview

Blues is an explainable, agentic research assistant that answers user queries using retrieved scientific evidence. 
Recently upgraded to feature a complete dual-pane persistent dashboard UI, strict enterprise-grade academic RAG generation, and robust memory context handling.

It combines:
- Planning (query decomposition into sub-questions)
- Hybrid retrieval (BM25 + Semantic + RRF)
- Sentence-level evidence extraction
- Structured generation (sub-question → paper → evidence)
- Verification and conflict detection (XAI)
- Local storage persistent application framework with seamless background generation caching.

Core promise: **grounded answers with traceable evidence**, not free-form hallucinated output.

---

## 2) Repository Structure

```text
Blues/
├── HANDOVER.md
├── CODE_CHANGES_SUMMARY.md
├── README.md
├── rag-backend/
│   ├── src/
│   │   ├── agents/               # Planner + verification agents
│   │   ├── chunking/             # Text chunking logic
│   │   ├── comparison/           # Conflict detection and comparison synthesis
│   │   ├── embeddings/           # Embedding model wrapper (SciBERT)
│   │   ├── evidence/             # Sentence-level evidence extraction
│   │   ├── export/               # Report generation/export helpers
│   │   ├── generation/           # Main answer generator + summarizer
│   │   ├── ingestion/            # Paper ingestion/fulltext collection
│   │   ├── llm/                  # LLM provider abstraction
│   │   ├── retrieval/            # Hybrid retrieval components (BM25Index)
│   │   ├── trace/                # Trace writer/reader
│   │   ├── api.py                # FastAPI routes
│   │   ├── main.py               # CLI entrypoint
│   │   └── config.py             # Runtime configuration
│   ├── tests/
│   └── pyproject.toml
└── rag-frontend/
    ├── src/
    │   ├── components/           # UI components (Panels, History)
    │   ├── services/             # API client methods
    │   ├── state/                # Workspace/Local Storage management
    │   ├── types/                # TS contracts
    │   ├── index.css             # Utility classes and custom themes
    │   └── App.tsx               # Primary Controller
    └── package.json
```

---

## 3) Backend Architecture (Detailed)

### 3.1 Request lifecycle
1. User sends query to API.
2. Planner decomposes query into sub-questions and search intents.
3. Hybrid retriever fetches candidate chunks utilizing FAISS Cosine distance combined with BM25 Lexical scoring.
4. Evidence extractor selects sentence-level support.
5. Generator builds structured response by sub-question.
6. Comparison/conflict layer adds XAI reasoning.
7. System generates an academic, emotion-less summary narrative over strict delimiter parsings.
8. Trace is persisted for reproducibility.

### 3.2 Major backend modules
- `src/api.py`: FastAPI endpoints. Orchestrates query, status, trace, and exports.
- `src/retrieval/hybrid_retriever.py`: Integrates dense vectors with sparse tokens using Reciprocal Rank Fusion. Ensures edge-case queries don't fail zero-evidence gates.
- `src/generation/generator.py`: Applies section and subquestion filtering mapping outputs against validation frameworks. Outputs trace evidence.
- `src/generation/summarizer.py`: Orchestrates cross-topic synthesis formatted cleanly via Markdown `==` delimiters.
- `src/trace/tracer.py`: Captures full execution logic tree.

---

## 4) Frontend Architecture (Detailed)

### 4.1 Stack
- React + TypeScript + Vite
- Lucide React standard Icons + Inter Textual displays structure over standard Tailwind.

### 4.2 UI flow
1. User navigates workspaces in left sidebar. Views specific history items or executes new queries.
2. Form actions communicate silently utilizing timeout-safe intervals.
3. System triggers layout-stable UI animations to populate specific analysis sections parsing exact structured chunks back from payload strings.
4. Final displays flag metrics like "Confidence score", "Trust Banding" directly connected to Trace elements.

### 4.3 Key UI components
- `components/ResultsPanel.tsx` — Handles regex-based text strip rendering and exact splitting over LLM logic payloads. Maps content directly into Lucide SVGs natively.
- `components/WorkspacePanels.tsx` — Drives modular UI elements such as `AnalysisHealthPanel` logic.
- `state/workspace.tsx` — Robust state framework bridging HTTP memory fetch calls with persistent LocalStorage UI triggers.

---

## 5) Current Capabilities

### Implemented and working
- Fully offline-capable UI/UX routing that correctly hooks API states.
- Exact Hybrid RAG algorithm scoring.
- Traceability reporting down to the specific `sentence_id` + heading location. 
- Fast start APIs batched loading into singleton modules.

### Focus metrics / Quality Controls
- Removed legacy "emojis" (`🔬, 📊`) injecting purely academic text.
- Reconfigured structural logic enforcing strict `type:topic | synthesis` validation against LLM formatting shifts.
- Corrected frontend timeline navigation where historical context fetching failed to switch active views.

---

## 6) API Summary (External Consumer View)
> Input contracts are stable. Retrieval architecture accepts multi-tenant project `local_user` indexing.

- Query execution (agentic answer generation logic).
- Status verification checks over local index thresholds.
- DB fetch/push mechanisms via FastAPI local sync schemas to Frontend's `WorkspaceProvider`.

---

## 7) How to Run Locally

### Backend (`rag-backend`)
```bash
cd rag-backend
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```
### Frontend (`rag-frontend`)
```bash
cd rag-frontend
npm run dev
```

---

## 8) Handover for Feedough (What to Emphasize)

Highlights to feature:
- **Differentiator:** Entirely Explainable. Does not rely on generic summarizations, but sentence bounded logic mapping utilizing BM25 + FAISS architecture.
- **Trust Features:** Pipeline displays logic pathways directly to end-user as XAI Trace logs nested in UI dashboard elements.
- **Enterprise Grade UX:** Fully modular workspace contexts mirroring best in class productivity apps. 

> “Blues is an explainable research assistant that decomposes complex queries, retrieves and verifies evidence across papers, and returns structured literature-style insights with traceable confidence.”
