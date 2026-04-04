# Bug Fixes - Quick Reference

## ✅ Bug 1: Sub-query Relevance Too Low
**Location**: `rag-backend/src/generation/generator.py` lines 29-31, 1122-1142

**Changes**:
```python
SUBQUERY_MATCH_THRESHOLD = 0.65    # was 0.50
SUBQUERY_STRONG_MATCH_THRESHOLD = 0.75  # was 0.60  
FALLBACK_TOP_K_PER_SUBQ = 0        # was 2
```

**Impact**: No more irrelevant padding. Missing evidence is transparent.

---

## ✅ Bug 2: Section Labels All Say "Methodology"
**Location**: `rag-backend/src/chunking/processor.py` lines 1-6, 20-27, 61-105, 157-214

**Key Change**: Added `_split_into_sections()` method that parses PDF headers:
- `## Introduction` → "introduction"
- `## Methodology` → "methodology"
- `## Results` → "results"
- `## Discussion` → "discussion"
- etc.

**Impact**: Chunks now labeled accurately at ingestion time.

---

## ✅ Bug 3: Results and Discussion Never Appear
**Location**: `rag-backend/src/generation/generator.py` lines 20-21, 248-258, 376-386

**Changes**:
```python
TOP_CHUNKS_PER_SECTION = 3       # was 2
MAX_SECTIONS_PER_PAPER = 5       # was 3
```

**Section preferences always include**: `{"results", "discussion"}`

**Impact**: Empirical findings now included in all queries.

---

## ✅ Bug 4: Comparison and Synthesis Identical
**Location**: 
- `rag-backend/src/generation/generator.py` lines 752-768
- `rag-backend/src/generation/summarizer.py` lines 18-88, 101-148

**Changes**:
- `_build_subquestion_conclusion()` → Returns data placeholder, not template text
- LLM prompt → New instruction: "Write ONE paragraph per sub-question with specific findings and method differences"
- `summarize()` → Passes sub-questions explicitly to LLM

**Impact**: 
- Comparison Summary = factual, cross-paper
- AI Research Summary = interpretive, per-subquestion insights

---

## Validation Checklist

- [ ] Run `pytest tests/test_generator.py -xvs` (should pass)
- [ ] Test query with narrow sub-question (should show "⚠ No sufficiently relevant evidence" if needed)
- [ ] Upload full-text PDF (should see diverse section labels in chunks)
- [ ] Compare output blocks (Comparison Summary ≠ AI Research Summary)
- [ ] Check that Results section appears in output
- [ ] Verify LLM synthesis mentions specific method names, not generic phrases

---

## Deployment Order

1. Deploy chunker fix (Bug 2) + new full-text PDFs
2. Deploy generator thresholds (Bug 1)
3. Deploy section preferences (Bug 3)
4. Deploy summarizer enhancement (Bug 4)

Or apply all at once if re-ingesting corpus.

---

## Key Files Changed

1. **processor.py** - Section detection at chunk time
2. **generator.py** - Thresholds, preferences, gating, conclusion format
3. **summarizer.py** - LLM prompt and sub-question passing

All changes backward compatible ✅
