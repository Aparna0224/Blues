# RAG Backend - Explainable AI Research Assistant# RAG Backend - Stage 1# RAG Backend - Stage 1# RAG Backend



A Retrieval-Augmented Generation (RAG) system for semantic search over academic papers with **sentence-level evidence extraction**.



## FeaturesRetrieval-Augmented Generation System - Stage 1 Implementation



### Stage 1: Core RAG Pipeline

- ✅ **Dual API Ingestion** - Fetch papers from OpenAlex AND Semantic Scholar

- ✅ **Text Chunking** - Split abstracts into 3-5 sentence chunks## OverviewRetrieval-Augmented Generation System - Stage 1 ImplementationRetrieval-Augmented Generation System Backend

- ✅ **SciBERT Embeddings** - 768-dimensional scientific text embeddings

- ✅ **FAISS Vector Search** - Fast similarity search with IndexFlatIP

- ✅ **MongoDB Storage** - Persistent paper and chunk storage

- ✅ **Answer Generation** - Create answers with citationsThis is a minimal RAG system that performs semantic search over academic papers using FAISS and MongoDB.



### Stage 2: Sentence-Level Evidence

- ✅ **Evidence Extraction** - Find the most relevant sentence per chunk

- ✅ **Sentence Similarity Scoring** - SciBERT-based sentence-level scores### Features## Overview## Setup

- ✅ **Dual Scoring** - Chunk similarity + Evidence similarity

- ✅ **NLTK Tokenization** - Robust sentence splitting



## Architecture✅ **Paper Ingestion** - Fetch papers from OpenAlex API  



```✅ **Text Chunking** - Split abstracts into 3-5 sentence chunks  

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐

│   OpenAlex API  │     │ Semantic Scholar│     │   MongoDB Atlas │✅ **Embedding Generation** - Generate SciBERT embeddings (768-dimensional)  This is a minimal RAG system that performs semantic search over academic papers using FAISS and MongoDB.1. Create virtual environment: `python -m venv venv`

└────────┬────────┘     └────────┬────────┘     └────────┬────────┘

         │                       │                       │✅ **Vector Search** - FAISS IndexFlatIP semantic search  

         └───────────┬───────────┘                       │

                     ▼                                   │✅ **Retrieval** - Fetch relevant chunks with similarity scores  2. Activate: `venv\Scripts\activate`

              ┌──────────────┐                          │

              │   Ingestor   │──────────────────────────┘✅ **Answer Generation** - Create answers with proper citations  

              └──────┬───────┘

                     ▼## Features3. Install dependencies: `pip install -r requirements.txt`

              ┌──────────────┐

              │   Chunker    │## Setup

              └──────┬───────┘

                     ▼4. Copy `.env.example` to `.env` and configure

              ┌──────────────┐     ┌─────────────────┐

              │   Embedder   │────►│   FAISS Index   │### 1. Create Virtual Environment with uv

              │   (SciBERT)  │     │  (768-dim)      │

              └──────────────┘     └────────┬────────┘✅ **Paper Ingestion** - Fetch papers from OpenAlex API5. Run: `python src/main.py`

                                            │

              ┌──────────────┐              │```bash

              │  Retriever   │◄─────────────┘

              └──────┬───────┘cd rag-backend✅ **Text Chunking** - Split abstracts into sentence-level chunks

                     ▼

              ┌──────────────┐uv venv✅ **Embedding Generation** - Generate SciBERT embeddings

              │  Evidence    │  ◄── Stage 2

              │  Extractor   │```✅ **Vector Search** - FAISS-based semantic search

              └──────┬───────┘

                     ▼✅ **Retrieval** - Fetch relevant chunks with similarity scores

              ┌──────────────┐

              │  Generator   │### 2. Activate Virtual Environment✅ **Answer Generation** - Create answers with citations

              └──────────────┘

```



## Setup```bash## Setup



### 1. Create Virtual Environment with uv# Windows



```bash.venv\Scripts\activate```bash

cd rag-backend

uv venvcd rag-backend

```

# macOS/Linuxuv venv

### 2. Activate Environment

source .venv/bin/activate.venv\Scripts\activate

**Windows (PowerShell):**

```powershell```uv pip sync pyproject.toml

.\.venv\Scripts\Activate.ps1

``````



**Linux/Mac:**### 3. Install Dependencies

```bash

source .venv/bin/activate## Configuration

```

```bash

### 3. Install Dependencies

uv pip sync pyproject.tomlCopy `.env.example` to `.env` and configure:

```bash

uv pip install -e .```

```

```

### 4. Configure Environment

### 4. Configure EnvironmentMONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/

Copy `.env.example` to `.env` and configure:

MONGO_DB=xai_rag

```env

# MongoDB AtlasCopy `.env.example` to `.env` and add your MongoDB credentials:```

MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=app



# OpenAlex API (uses mailto for polite pool)

OPENALEX_EMAIL=your-email@example.com```bash## Usage



# Semantic Scholar API (optional - for higher rate limits)cp .env.example .env

SEMANTIC_SCHOLAR_API_KEY=your-api-key

`````````bash



## CLI Commands# Ingest papers



### Ingest PapersEdit `.env`:python -m src.main ingest --query "machine learning"



```bash```env

# From OpenAlex (default)

python -m src.main ingest --query "machine learning" --max-results 10MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/# Build FAISS index



# From Semantic ScholarMONGO_DB=xai_ragpython -m src.main build-index

python -m src.main ingest --query "deep learning" --source semantic_scholar

DEBUG=True

# From BOTH APIs (recommended)

python -m src.main ingest --query "neural networks" --source both --max-results 20```# Query the system

```

python -m src.main query --query "What is deep learning?"

### Build FAISS Index

## Project Structure

```bash

python -m src.main build-index# Check status

```

```python -m src.main status

### Query the System

rag-backend/

```bash

# Stage 1: Chunk-level retrieval├── src/# Reset data

python -m src.main query --query "What is deep learning?"

│   ├── __init__.pypython -m src.main reset

# Stage 2: Sentence-level evidence (recommended)

python -m src.main query --query "What is deep learning?" --evidence│   ├── main.py                 # CLI entry point```

```

│   ├── config.py               # Configuration management

### Check Status

│   ├── database.py             # MongoDB connection (singleton)## Project Structure

```bash

python -m src.main status│   ├── vector_store.py         # FAISS index operations

```

│   ├── ingestion/```

### Reset Data

│   │   ├── __init__.pysrc/

```bash

python -m src.main reset│   │   └── loader.py           # PaperIngestor class├── main.py                  # CLI interface

```

│   ├── chunking/├── config.py               # Configuration

## Stage 2: Evidence Extraction

│   │   ├── __init__.py├── database.py             # MongoDB connection

The `--evidence` flag enables sentence-level evidence extraction:

│   │   └── processor.py        # TextChunker class├── vector_store.py         # FAISS management

```bash

python -m src.main query --query "How do neural networks learn?" --evidence│   ├── embeddings/├── ingestion/loader.py     # Paper ingestion

```

│   │   ├── __init__.py├── chunking/processor.py   # Text chunking

**Output includes:**

- **Chunk Similarity**: FAISS-based chunk-level score│   │   └── embedder.py         # EmbeddingGenerator class├── embeddings/embedder.py  # Embedding generation

- **Evidence Score**: Sentence-level similarity to query

- **Evidence Sentence**: The most relevant sentence from each chunk│   ├── retrieval/├── retrieval/retriever.py  # Semantic search



Example output:│   │   ├── __init__.py└── generation/generator.py # Answer generation

```

==============================================================================│   │   └── retriever.py        # Retriever class```

SENTENCE-LEVEL EVIDENCE

==============================================================================│   └── generation/



[1] Deep Learning (2016)│       ├── __init__.py## Dependencies

    Chunk Similarity: 0.6814

    Evidence Score: 0.7139│       └── generator.py        # AnswerGenerator class

    Evidence: "Neural networks learn through backpropagation by adjusting weights."

├── pyproject.toml- Python 3.11+

[2] Neural Network Fundamentals (2022)

    Chunk Similarity: 0.6527├── .env.example- MongoDB Atlas

    Evidence Score: 0.6892

    Evidence: "The learning process involves minimizing a loss function."└── README.md- FAISS

```

```- sentence-transformers

## API Sources

- pymongo

### OpenAlex

- **Rate Limit**: 100k requests/day with mailto (polite pool)## Usage- nltk

- **Fields**: title, abstract, year, citation count

- **Note**: Abstracts are stored as inverted index - automatically converted- numpy



### Semantic Scholar### 1. Ingest Papers

- **Rate Limit**: 100 requests/5 min (unauthenticated), higher with API key

- **Retry Logic**: Automatic retry with exponential backoff for 429 errorsSee `pyproject.toml` for full list.



## Project Structure```bash



```python -m src.main ingest --query "machine learning" --max-results 10## See Also

rag-backend/

├── src/```

│   ├── __init__.py

│   ├── config.py           # Configuration from .env- `QUICKSTART.md` - Quick start guide

│   ├── database.py          # MongoDB connection

│   ├── main.py              # CLI entry point### 2. Build FAISS Index- `STAGE1_COMPLETE.md` - Stage 1 details

│   ├── vector_store.py      # FAISS index management

│   ├── chunking/- `FOLDER_STRUCTURE.md` - Directory structure

│   │   └── processor.py     # Text chunking

│   ├── embeddings/```bash

│   │   └── embedder.py      # SciBERT embeddingspython -m src.main build-index

│   ├── evidence/```

│   │   └── extractor.py     # Stage 2: Sentence evidence

│   ├── generation/### 3. Query the System

│   │   └── generator.py     # Answer generation

│   ├── ingestion/```bash

│   │   └── loader.py        # Dual API ingestionpython -m src.main query --query "What is the definition of machine learning?" --top-k 5

│   └── retrieval/```

│       └── retriever.py     # Semantic search

├── tests/### 4. Check System Status

│   └── test_evidence.py     # Unit tests (21 tests)

├── data/```bash

│   └── faiss_index.bin      # FAISS index filepython -m src.main status

├── output/```

│   └── rag_output.txt       # Query results

├── pyproject.toml           # Dependencies (uv)### 5. Reset System

└── .env                     # Environment config

``````bash

python -m src.main reset

## Running Tests```



```bash## Database Schema

# Run all tests

python -m pytest tests/ -v### papers collection

```json

# Run evidence tests only{

python -m pytest tests/test_evidence.py -v  "paper_id": "string",

```  "title": "string",

  "abstract": "string",

## Dependencies  "year": "int",

  "citation_count": "int",

- **sentence-transformers**: SciBERT embeddings  "source": "string"

- **faiss-cpu**: Vector similarity search}

- **pymongo**: MongoDB Atlas connection```

- **nltk**: Sentence tokenization

- **click**: CLI framework### chunks collection

- **requests**: API calls```json

{

## Environment Variables  "chunk_id": "string (UUID)",

  "paper_id": "string",

| Variable | Description | Default |  "text": "string",

|----------|-------------|---------|  "section": "abstract",

| `MONGO_URI` | MongoDB connection string | Required |  "embedding_index": "int (FAISS row position)"

| `OPENALEX_EMAIL` | Email for OpenAlex polite pool | Required |}

| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API key | Optional |```

| `FAISS_INDEX_PATH` | Path to FAISS index | `./data/faiss_index.bin` |

| `EMBEDDING_MODEL` | Embedding model name | `allenai/scibert_scivocab_uncased` |## Architecture

| `TOP_K` | Default chunks to retrieve | `5` |

### Query Flow

## License```

User Query

MIT License    ↓

Embed Query (SciBERT)
    ↓
FAISS Search (IndexFlatIP)
    ↓
Retrieve Chunk IDs
    ↓
MongoDB Metadata Lookup
    ↓
Build Context
    ↓
Generate Answer with Citations
```

### Ingestion Flow
```
OpenAlex API
    ↓
Normalize Paper
    ↓
Store in MongoDB (papers collection)
    ↓
Chunk Abstract (3-5 sentences)
    ↓
Store in MongoDB (chunks collection)
    ↓
Generate Embeddings (SciBERT)
    ↓
Store in FAISS IndexFlatIP
```

## Tech Stack

- **Python** 3.11+
- **MongoDB Atlas** - Cloud database
- **FAISS** - Vector search (IndexFlatIP with inner product metric)
- **sentence-transformers** - SciBERT model (allenai/scibert_scivocab_uncased)
- **pymongo** - MongoDB driver
- **requests** - HTTP client for OpenAlex API
- **nltk** - Sentence tokenization
- **numpy** - Numerical operations
- **python-dotenv** - Environment variable management
- **click** - CLI framework

## Implementation Notes

- **Singleton Pattern**: MongoDB client uses singleton pattern to ensure single connection
- **Normalization**: All embeddings are L2-normalized for cosine similarity
- **Chunking Strategy**: Abstracts split into 3-5 sentence chunks
- **Citation Format**: `[Paper Title, Year]`
- **No API Key Required**: OpenAlex API is free and doesn't require authentication

## Limitations (Not Implemented)

- ❌ No agents
- ❌ No verification logic
- ❌ No trace logging
- ❌ No UI
- ❌ No multi-hop retrieval
- ❌ No hallucination detection

## Testing

Run the commands in sequence to test the system:

```bash
# 1. Ingest 5 papers
python -m src.main ingest --query "deep learning" --max-results 5

# 2. Build index
python -m src.main build-index

# 3. Check status
python -m src.main status

# 4. Query
python -m src.main query --query "What is deep learning?" --top-k 3
```

## Troubleshooting

### MongoDB Connection Error
- Check `.env` file has correct `MONGO_URI`
- Ensure MongoDB Atlas cluster is accessible from your IP
- Verify network access in MongoDB Atlas security settings

### Out of Memory Error During Embedding
- Reduce `max_results` in ingest command
- Process papers in smaller batches
- Increase available system memory

### FAISS Index Not Found
- Run `build-index` command first
- Check `FAISS_INDEX_PATH` in `.env`

## Author

Built as part of Stage 1 RAG implementation.

## License

MIT
