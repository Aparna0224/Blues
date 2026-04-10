# 📄 HANDOVER.md (Production-Grade)

## 1. Project Overview

### Title

**Agentic RAG Research System with Verification Loop**

### Objective

This system upgrades a traditional RAG pipeline into a **fully agentic research system** capable of:

* Planning research queries
* Retrieving multi-source knowledge
* Generating structured answers
* Verifying factual correctness
* Expanding weak areas iteratively
* Producing final summarized output

### Core Concept

Unlike standard RAG, this system:

* Uses **LangGraph orchestration**
* Implements **multi-step reasoning loops**
* Includes **self-verification and expansion cycles**

---

## 2. Tech Stack

| Layer           | Technology                     |
| --------------- | ------------------------------ |
| Backend         | FastAPI                        |
| Orchestration   | LangGraph                      |
| LLM             | Ollama (DeepSeek / Mistral)    |
| Embeddings      | Ollama / Sentence Transformers |
| Vector DB       | FAISS / Chroma                 |
| Database        | MongoDB                        |
| Frontend        | React                          |
| Async Execution | asyncio                        |

---

## 3. High-Level Architecture

```text
User Query
   ↓
Planner Node
   ↓
Retriever Node (parallel)
   ↓
Generator Node
   ↓
Verifier Node
   ↓
 ┌───────────────┐
 ↓               ↓
Expand Node     Summarize Node
 ↓
Generator (loop)
```

---

## 4. LangGraph Flow Design

### Nodes Implemented

#### 1. `plan`

* Breaks user query into sub-questions
* Output: structured plan

#### 2. `retrieve`

* Runs **parallel retrieval**
* Sources:

  * Vector DB
  * External APIs (optional)
* Uses `asyncio.gather`

#### 3. `generate`

* Produces answers using LLM
* Combines retrieved context

#### 4. `verify`

* Checks:

  * Missing information
  * Unsupported claims
* Outputs:

  * `needs_expansion: true/false`
  * `missing_topics: []`

#### 5. `expand`

* Generates new queries for missing gaps
* Loops back to retrieve → generate

#### 6. `summarize`

* Produces final clean output

---

## 5. State Schema (CRITICAL)

```python
class GraphState(TypedDict):
    query: str
    plan: list
    retrieved_docs: list
    generated_answer: str
    verification: dict
    expanded_queries: list
    final_answer: str
```

---

## 6. Key Features Implemented

### Agentic Loop

* Conditional edge:

```python
if verification["needs_expansion"]:
    go to expand
else:
    go to summarize
```

### Parallel Retrieval

```python
await asyncio.gather(
    retrieve_vector(),
    retrieve_external()
)
```

### Iterative Improvement

* Expand → Generate loop continues until:

  * No missing info
  * OR max iterations reached

---

## 7. Current Issues (VERY IMPORTANT)

### Issue 1: Repetitive Output

* Same sub-question repeated:

```text
⚠ No specific evidence found for this sub-question
```

#### Possible Causes

* Retrieval failure
* Poor embedding match
* Verifier too strict
* Expand generating duplicate queries

---

### Issue 2: Weak Retrieval Quality

* Missing relevant documents
* Low semantic match

---

### Issue 3: Over-Summarization

* System synthesizes instead of showing raw evidence

---

### Issue 4: Improper JSON Handling (FastAPI + LLM)

* LLM output not structured properly
* Causes parsing issues

---

## 8. Expected Behavior

The system should:

* NOT repeat sub-questions
* Provide **evidence-backed answers**
* Avoid hallucinations
* Expand only when necessary
* Return structured, clean output

---

## 9. What Needs to be Fixed

### Priority Fixes

1. **Deduplicate sub-questions**
2. Improve retrieval relevance
3. Fix verifier logic (too aggressive)
4. Ensure expand generates NEW queries
5. Enforce structured LLM output
6. Stop empty responses propagation

---

## 10. Constraints

* Must work with local LLM (Ollama)
* Must support async execution
* Must be production-safe (no crashes)
* Must return JSON-compatible output

---

## 11. Files to Focus On

* `graph.py` → LangGraph pipeline
* `retriever.py` → retrieval logic
* `generator.py` → LLM calls
* `verifier.py` → validation logic
* `expand.py` → query expansion
* `main.py` → FastAPI integration

---

## 12. Debug Strategy

1. Log each node output
2. Validate state transitions
3. Print verification decisions
4. Track duplicate queries
5. Inspect embeddings similarity scores

---

# 🚀 MASTER PROMPT FOR CLAUDE / LLM

Use this prompt directly:

---

## 🔥 SYSTEM PROMPT

You are a senior AI systems engineer specializing in:

* Agentic RAG systems
* LangGraph orchestration
* LLM pipelines
* Retrieval optimization
* Debugging production AI systems

You must:

* Analyze deeply
* Identify root causes (not surface issues)
* Provide exact fixes (code-level if needed)
* Avoid generic advice

---

## 📥 INPUT CONTEXT

I am providing you with a full project handover.

This is an **Agentic RAG system** built using:

* LangGraph
* FastAPI
* Ollama (DeepSeek / Mistral)
* FAISS/Chroma

The system includes:

* Planner
* Retriever (parallel)
* Generator
* Verifier
* Expand loop
* Summarizer

---

## 🚨 PROBLEMS TO FIX

1. Repeated sub-questions:

   * "No specific evidence found..."
   * Same questions appearing multiple times

2. Weak retrieval:

   * Missing relevant context

3. Over-synthesis:

   * I want evidence, not summaries

4. Verifier issues:

   * Too aggressive → unnecessary expansion

5. Expand loop:

   * Generates duplicate queries

6. JSON output issues:

   * LLM output not structured properly

---

## 🎯 YOUR TASK

Perform the following:

### 1. Root Cause Analysis

* Explain WHY each issue is happening
* Trace through pipeline stages

### 2. Pipeline Fixes

* Suggest exact improvements for:

  * Retrieval
  * Verification
  * Expansion logic
  * Deduplication

### 3. Code-Level Fixes

Provide:

* Updated functions
* Improved prompts
* Better state handling

### 4. Prompt Engineering Fixes

* Fix generator prompt
* Fix verifier prompt
* Fix expand prompt

### 5. Optimization

* Improve:

  * Latency
  * Accuracy
  * Stability

### 6. Output Format Fix

* Ensure strict JSON output

---

## ⚠️ CONSTRAINTS

* Do NOT redesign entire system
* Work within current architecture
* Must support local LLM (Ollama)
* Must be async-compatible

---

## ✅ EXPECTED OUTPUT

* Clear diagnosis
* Step-by-step fixes
* Code snippets
* Improved prompts
* Final improved pipeline design

---

# 🧠 Optional Add-on (Highly Recommended)

Include this in your prompt:

```text
Also suggest evaluation metrics for:
- Retrieval quality
- Answer correctness
- Expansion efficiency
```

---

# ✔️ Final Note

This handover is designed so that:

* A **new engineer** can onboard instantly
* An **LLM like Claude** can debug effectively
* Your system moves from **prototype → production-grade agent**
