# Fix Plan — 13 Issues (All Complete ✅)

## Critical (1–3) — ~380s savings

### ✅ Fix 1: SciBERT singleton
- **Files**: `src/embeddings/embedder.py`, `src/evidence/extractor.py`, `src/generation/generator.py`, `src/retrieval/dynamic_retriever.py`, `src/retrieval/retriever.py`, `src/main.py`, `src/api.py`
- EmbeddingGenerator is now a singleton — model loads once, shared everywhere via `get_shared_embedder()`

### ✅ Fix 2: Skip re-embedding existing chunks
- **File**: `src/retrieval/dynamic_retriever.py`
- Embeddings stored in MongoDB alongside chunks
- Existing embeddings loaded from DB, only new chunks get embedded
- Uses `embed_batch()` instead of per-chunk `embed_text()` calls

### ✅ Fix 3: Filter junk evidence sentences
- **File**: `src/evidence/extractor.py`
- Added `_is_junk_sentence()` filter that drops:
  - Sentences under 8 words
  - Citation-like patterns (Vol., doi:, et al., ISSN, arXiv, etc.)
  - Mostly uppercase sentences (>60% uppercase)
  - Mostly numeric sentences (>50% digits)

## High (4–7) — Literature review quality

### ✅ Fix 4: Broaden RELEVANCE_TERMS
- **File**: `src/agents/verification.py`
- Added RAG, NLP, general AI, and research terms to static list
- Added dynamic term extraction from query + sub-questions

### ✅ Fix 5: Increase top_k for agentic queries
- **File**: `src/api.py`
- effective_top_k = max(num_documents, num_sub_questions × 5, 15)

### ✅ Fix 6: Lower MULTI_ASSIGN_RATIO + enforce diversity
- **File**: `src/generation/generator.py`
- MULTI_ASSIGN_RATIO: 0.95 → 0.80
- Exclusive primary assignment: each chunk goes to its best sub-question first
- Multi-assignment only if score is within 20% AND target sub-q has room
- MAX_CHUNKS_PER_SUBQ = 5 cap

### ✅ Fix 7: Fix empty summary
- **File**: `src/generation/summarizer.py`
- Detects LLM error strings leaked as content
- Always returns non-empty fallback message

## Medium (8–10) — Stability

### ✅ Fix 8: Groq errors as exceptions
- **File**: `src/llm/groq_llm.py`
- All error paths now raise RuntimeError/ConnectionError instead of returning strings

### ✅ Fix 9: MongoDB connecting redundantly
- **File**: `src/database.py`
- `connect()` now returns immediately if `self.initialized` is True

### ✅ Fix 10: Load persisted FAISS index on startup
- **File**: `src/vector_store.py`
- FAISSVectorStore is now a singleton
- Index path resolved as absolute path (avoids working-directory issues)
- Prints vector count on load

## Low (11–13) — Polish

### ✅ Fix 11: Batch evidence extraction
- **File**: `src/evidence/extractor.py`
- `extract_evidence_from_chunks()` now collects ALL sentences, embeds in 1 batch, slices back

### ✅ Fix 12: Chunk-level embedding reuse for cached papers
- **File**: `src/retrieval/dynamic_retriever.py`
- Expanded reuse logic: checks for existing chunks AND body sections
- Only re-chunks papers with newly-downloaded full text

### ✅ Fix 13: Stricter PDF cleaning
- **File**: `src/ingestion/fulltext.py`
- Repeated-line threshold: >3 → >1
- Added regex-based artifact removal for journal headers, DOIs, copyright, publisher lines
