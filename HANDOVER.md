# Blues — Full Project Handover (Backend + Frontend)

Prepared for: External product/content review (Feedough)
Project: **Blues**
Type: **Agentic RAG Research Assistant**

---

## 1) Product Overview

Blues is an explainable, agentic research assistant that answers user queries using retrieved scientific evidence.

It combines:

- Planning (query decomposition into sub-questions)
- Hybrid retrieval (BM25 + semantic + RRF)
- Sentence-level evidence extraction
- Structured generation (sub-question → paper → evidence)
- Verification and conflict detection (XAI)
- Export-ready output (summary + evidence + references)

Core promise: **grounded answers with traceable evidence**, not free-form hallucinated output.

---

## 2) Repository Structure

```text
Blues/
├── HANDOVER.md
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
│   │   ├── retrieval/            # Hybrid retrieval components
│   │   ├── trace/                # Trace writer/reader
│   │   ├── api.py                # FastAPI routes
│   │   ├── main.py               # CLI entrypoint
│   │   └── config.py             # Runtime configuration
│   ├── tests/
│   └── pyproject.toml
└── rag-frontend/
    ├── src/
    │   ├── components/           # UI components
    │   ├── services/             # API client
    │   ├── types/                # TS contracts
    │   └── App.tsx
    └── package.json
```

---

## 3) Backend Architecture (Detailed)

### 3.1 Request lifecycle

1. User sends query to API.
2. Planner decomposes query into sub-questions and search intents.
3. Hybrid retriever fetches candidate chunks.
4. Evidence extractor selects sentence-level support.
5. Generator builds structured response by sub-question.
6. Comparison/conflict layer adds XAI reasoning.
7. Verification calculates confidence and quality metrics.
8. Trace is persisted for reproducibility.

### 3.2 Major backend modules

- `src/api.py`
  - FastAPI endpoints
  - orchestrates query, status, trace, and export paths

- `src/agents/planner.py`
  - Converts one broad query into sub-questions + search queries

- `src/retrieval/`
  - Hybrid retrieval stack (BM25 + semantic + RRF)
  - Supports cached and dynamic modes
  - **Note**: retrieval logic is stable and intentionally separated from generation

- `src/evidence/extractor.py`
  - Sentence tokenization
  - similarity scoring for evidence sentence selection
  - cleaning/robust fallback behavior for dependency variance

- `src/generation/generator.py`
  - maps chunks to sub-questions
  - applies per-subquestion filtering
  - fallback reassignment when a sub-question would otherwise be empty
  - builds structured, human-readable evidence blocks
  - emits confidence labels and synthesis sections

- `src/comparison/conflict_detector.py`
  - cross-paper pairwise conflict detection
  - conceptual/methodological/empirical conflict typing
  - comparison summary synthesis grounded in evidence units

- `src/generation/summarizer.py`
  - final narrative summary generation (evidence-grounded)

- `src/export/report_builder.py`
  - report construction for downloadable formats (Markdown/PDF workflow support)

- `src/trace/tracer.py`
  - captures full execution trace (planning/retrieval/filtering/evidence/verification)

### 3.3 Data quality and explainability

Backend enforces:

- sub-question-aware assignment and scoring
- no empty `sub_question` assignment in mapped units
- conflict analysis with rationale
- confidence bands (`High` / `Medium` / `Low`)
- paper-level traceability (`paper_id`, `paper_title`, location metadata)

---

## 4) Frontend Architecture (Detailed)

### 4.1 Stack

- React + TypeScript + Vite
- Component-driven rendering of analysis outputs

### 4.2 UI flow

1. User enters query and mode/options.
2. Frontend calls backend query API.
3. Results view displays:
   - sub-question sections
   - grouped paper evidence
   - confidence/verification indicators
   - comparison/conflict outputs
   - global summary
4. User can inspect papers, evidence blocks, and status details.

### 4.3 Key UI components

- `components/QueryForm.tsx` — input and query execution controls
- `components/ResultsPanel.tsx` — core structured answer rendering
- `components/VerificationCard.tsx` — confidence + quality metrics
- `components/SummaryPanel.tsx` — final summary block
- `components/PapersTable.tsx` — evidence source list
- `components/StatusBar.tsx` — backend/system status
- `components/FileUpload.tsx` — ingestion/upload utility

---

## 5) Current Capabilities

### Implemented and working

- Hybrid retrieval path integrated in backend
- Structured grouped generation output
- Cross-paper comparison and conflict detection (XAI)
- Trace generation for debugging/audit
- Focused quality tests passing for generator/evidence/conflict modules

### Stability checks from latest run context

- Focused test set passed:
  - `tests/test_generator.py`
  - `tests/test_evidence.py`
  - `tests/test_conflict_detector.py`

---

## 6) API Summary (External Consumer View)

> Input contracts are stable; retrieval internals are abstracted behind API.

Common endpoint categories:

- Query execution (agentic answer generation)
- Health/status
- Trace retrieval by execution id
- Report download/export endpoints (format-driven)

The frontend uses `src/services/api.ts` as the single API integration layer.

---

## 7) How to Run Locally

### Backend (`rag-backend`)

1. Create env and install deps
2. Configure `.env`
3. Run API server

Known working server command in current context:

```bash
cd /home/aparna/Documents/project/Blues/rag-backend
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (`rag-frontend`)

```bash
cd /home/aparna/Documents/project/Blues/rag-frontend
npm install
npm run dev
```

---

## 8) Testing & Quality

### Focused backend tests (recently green)

```bash
cd /home/aparna/Documents/project/Blues/rag-backend
pytest tests/test_generator.py tests/test_evidence.py tests/test_conflict_detector.py -q
```

### Full-suite note

If full hybrid retrieval tests fail with `rank_bm25` import errors, treat as environment dependency setup issue and install missing packages before final regression sign-off.

---

## 9) Known Limitations / Risks

1. Environment-dependent package availability can affect full suite runs.
2. Query-domain drift may require threshold tuning for best evidence assignment quality.
3. Summary quality depends on evidence quality and source diversity of retrieved chunks.

---

## 10) Handover for Feedough (What to Emphasize)

If this project is being reviewed for product showcase/content publication, highlight:

- **Differentiator:** evidence-grounded agentic RAG with explainability, not just generic chat.
- **Trust features:** sentence-level citations, conflict analysis, confidence labels, execution traces.
- **User value:** structured, research-style outputs with paper-level references.
- **Product readiness:** API-backed architecture + frontend UI + export/report capability.

Suggested one-line pitch:

> “Blues is an explainable research assistant that decomposes complex queries, retrieves and verifies evidence across papers, and returns structured literature-style insights with traceable confidence.”

---

## 11) Suggested Next Milestones

1. Finalize full export UX (PDF/Markdown download controls) in frontend if pending.
2. Run full backend + frontend QA regression in a normalized environment.
3. Add lightweight E2E tests for query → render → export workflow.
4. Prepare public demo script with 2–3 domain queries (e.g., biomedical + AI systems).

---

## 12) Contacts / Ownership (To Fill Before Sharing)

- Backend owner:
- Frontend owner:
- Product/demo owner:
- Deployment environment:
- Last verified date:
