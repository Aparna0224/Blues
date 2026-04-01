# RAG Frontend# React + TypeScript + Vite



React + TypeScript UI for the Blues XAI-Enhanced Agentic RAG Research Assistant. Provides a single-page interface for querying the research pipeline, viewing verification metrics, browsing source papers, and reading pipeline summaries.This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.



---Currently, two official plugins are available:



## Quick Start- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh

- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

```bash

cd rag-frontend## React Compiler

npm install

npm run devThe React Compiler is enabled on this template. See [this documentation](https://react.dev/learn/react-compiler) for more information.

```

Note: This will impact Vite dev & build performances.

Open **http://localhost:5173** — requires the backend running on port 8000.

## Expanding the ESLint configuration

---

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

## Scripts

```js

| Command | Description |export default defineConfig([

|---------|-------------|  globalIgnores(['dist']),

| `npm run dev` | Start Vite dev server with HMR (port 5173) |  {

| `npm run build` | Type-check (`tsc -b`) + production build |    files: ['**/*.{ts,tsx}'],

| `npm run preview` | Serve the production build locally |    extends: [

| `npm run lint` | Run ESLint |      // Other configs...



---      // Remove tseslint.configs.recommended and replace with this

      tseslint.configs.recommendedTypeChecked,

## API Proxy      // Alternatively, use this for stricter rules

      tseslint.configs.strictTypeChecked,

Vite proxies `/api` requests to the backend (configured in `vite.config.ts`):      // Optionally, add this for stylistic rules

      tseslint.configs.stylisticTypeChecked,

```

Browser → http://localhost:5173/api/query      // Other configs...

                ↓ (Vite proxy)    ],

Backend → http://localhost:8000/api/query    languageOptions: {

```      parserOptions: {

        project: ['./tsconfig.node.json', './tsconfig.app.json'],

In production, configure your reverse proxy (nginx, etc.) to forward `/api` to the backend.        tsconfigRootDir: import.meta.dirname,

      },

---      // other options...

    },

## Components  },

])

| Component | File | Description |```

|-----------|------|-------------|

| **QueryForm** | `QueryForm.tsx` | Research question input, mode selector (dynamic/static), document count slider, summary toggle |You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

| **ResultsPanel** | `ResultsPanel.tsx` | Renders the grouped answer (Markdown), shows execution ID and chunk count |

| **VerificationCard** | `VerificationCard.tsx` | Confidence score badge (HIGH/MEDIUM/LOW), 4 metrics gauges, conflict warnings, full audit trail |```js

| **PapersTable** | `PapersTable.tsx` | Source papers with title, authors, year, DOI links |// eslint.config.js

| **SummaryPanel** | `SummaryPanel.tsx` | LLM-generated pipeline narrative summary |import reactX from 'eslint-plugin-react-x'

| **LoadingSpinner** | `LoadingSpinner.tsx` | Animated spinner with status message |import reactDom from 'eslint-plugin-react-dom'

| **StatusBar** | `StatusBar.tsx` | System health — MongoDB status, vector count, LLM provider |

| **FileUpload** | `FileUpload.tsx` | PDF upload with drag-and-drop for paper ingestion |export default defineConfig([

  globalIgnores(['dist']),

---  {

    files: ['**/*.{ts,tsx}'],

## Type Definitions    extends: [

      // Other configs...

All types are in `src/types/index.ts` and match the backend API response shape:      // Enable lint rules for React

      reactX.configs['recommended-typescript'],

```      // Enable lint rules for React DOM

QueryResponse      reactDom.configs.recommended,

├── execution_id, status, total_time_ms    ],

├── planning: { main_question, sub_questions, search_queries, latency_ms }    languageOptions: {

├── grouped_answer: string (Markdown)      parserOptions: {

├── chunks_used: number        project: ['./tsconfig.node.json', './tsconfig.app.json'],

├── papers_found: PaperInfo[]        tsconfigRootDir: import.meta.dirname,

├── verification: VerificationResult      },

│   ├── confidence_score: number      // other options...

│   ├── metrics: VerificationMetrics    },

│   │   ├── avg_similarity, source_diversity  },

│   │   ├── normalized_source_diversity, evidence_density])

│   │   └── conflicts_detected: string[]```

│   ├── warnings: string[]
│   └── audit: VerificationAudit
│       ├── total_claims_received, claims_after_dedup
│       ├── claims_after_relevance_filter
│       ├── claims_above_similarity_threshold
│       ├── claims_used_for_scoring, claims_rejected
├── summary?: string
└── warnings: string[]
```

---

## Project Structure

```
rag-frontend/
├── index.html                      ← Entry HTML
├── package.json                    ← Dependencies
├── vite.config.ts                  ← Vite config + API proxy
├── tsconfig.json                   ← TypeScript config (references)
├── tsconfig.app.json               ← App-level TS config
├── tsconfig.node.json              ← Node/Vite TS config
├── eslint.config.js                ← ESLint flat config
│
├── public/                         ← Static assets
│
└── src/
    ├── main.tsx                    ← React entry point
    ├── App.tsx                     ← Root component — layout + state
    ├── index.css                   ← Tailwind CSS v4 imports
    │
    ├── components/
    │   ├── QueryForm.tsx           ← Query input + options
    │   ├── ResultsPanel.tsx        ← Answer display (Markdown)
    │   ├── VerificationCard.tsx    ← Confidence + metrics + audit
    │   ├── PapersTable.tsx         ← Source papers table
    │   ├── SummaryPanel.tsx        ← Pipeline summary
    │   ├── LoadingSpinner.tsx      ← Loading indicator
    │   ├── StatusBar.tsx           ← System health bar
    │   └── FileUpload.tsx          ← PDF upload
    │
    ├── services/
    │   └── api.ts                  ← Axios client + error handling
    │
    └── types/
        └── index.ts                ← TypeScript interfaces
```

---

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2.0 | UI framework |
| TypeScript | 5.9.3 | Type safety |
| Vite | 7.3.1 | Build tool + dev server |
| Tailwind CSS | v4 | Utility-first styling |
| axios | 1.13.6 | HTTP client |
| lucide-react | 0.575.0 | Icons |

---

## Key Implementation Details

### Confidence Labels

`VerificationCard` computes labels on the frontend:

| Score | Label | Color |
|-------|-------|-------|
| ≥ 0.75 | HIGH | Green |
| ≥ 0.50 | MEDIUM | Yellow |
| < 0.50 | LOW | Red |

### Error Handling

`services/api.ts` exports `extractErrorMessage()` which unwraps axios errors into user-friendly strings — displayed in the UI via the results panel.

### Summary Toggle

The query form includes a "Generate Summary" checkbox (defaults to **on**). When enabled, the backend runs the PipelineSummarizer to produce a 100–200 word narrative after answer generation.

---

## Environment Requirements

- **Node.js** 18+
- **npm** 9+
- Backend running on `http://localhost:8000` (see [backend README](../rag-backend/README.md))
