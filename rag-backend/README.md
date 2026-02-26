# RAG Backend - Stage 1# RAG Backend - Stage 1# RAG Backend



Retrieval-Augmented Generation System - Stage 1 Implementation



## OverviewRetrieval-Augmented Generation System - Stage 1 ImplementationRetrieval-Augmented Generation System Backend



This is a minimal RAG system that performs semantic search over academic papers using FAISS and MongoDB.



### Features## Overview## Setup



✅ **Paper Ingestion** - Fetch papers from OpenAlex API  

✅ **Text Chunking** - Split abstracts into 3-5 sentence chunks  

✅ **Embedding Generation** - Generate SciBERT embeddings (768-dimensional)  This is a minimal RAG system that performs semantic search over academic papers using FAISS and MongoDB.1. Create virtual environment: `python -m venv venv`

✅ **Vector Search** - FAISS IndexFlatIP semantic search  

✅ **Retrieval** - Fetch relevant chunks with similarity scores  2. Activate: `venv\Scripts\activate`

✅ **Answer Generation** - Create answers with proper citations  

## Features3. Install dependencies: `pip install -r requirements.txt`

## Setup

4. Copy `.env.example` to `.env` and configure

### 1. Create Virtual Environment with uv

✅ **Paper Ingestion** - Fetch papers from OpenAlex API5. Run: `python src/main.py`

```bash

cd rag-backend✅ **Text Chunking** - Split abstracts into sentence-level chunks

uv venv✅ **Embedding Generation** - Generate SciBERT embeddings

```✅ **Vector Search** - FAISS-based semantic search

✅ **Retrieval** - Fetch relevant chunks with similarity scores

### 2. Activate Virtual Environment✅ **Answer Generation** - Create answers with citations



```bash## Setup

# Windows

.venv\Scripts\activate```bash

cd rag-backend

# macOS/Linuxuv venv

source .venv/bin/activate.venv\Scripts\activate

```uv pip sync pyproject.toml

```

### 3. Install Dependencies

## Configuration

```bash

uv pip sync pyproject.tomlCopy `.env.example` to `.env` and configure:

```

```

### 4. Configure EnvironmentMONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/

MONGO_DB=xai_rag

Copy `.env.example` to `.env` and add your MongoDB credentials:```



```bash## Usage

cp .env.example .env

``````bash

# Ingest papers

Edit `.env`:python -m src.main ingest --query "machine learning"

```env

MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/# Build FAISS index

MONGO_DB=xai_ragpython -m src.main build-index

DEBUG=True

```# Query the system

python -m src.main query --query "What is deep learning?"

## Project Structure

# Check status

```python -m src.main status

rag-backend/

├── src/# Reset data

│   ├── __init__.pypython -m src.main reset

│   ├── main.py                 # CLI entry point```

│   ├── config.py               # Configuration management

│   ├── database.py             # MongoDB connection (singleton)## Project Structure

│   ├── vector_store.py         # FAISS index operations

│   ├── ingestion/```

│   │   ├── __init__.pysrc/

│   │   └── loader.py           # PaperIngestor class├── main.py                  # CLI interface

│   ├── chunking/├── config.py               # Configuration

│   │   ├── __init__.py├── database.py             # MongoDB connection

│   │   └── processor.py        # TextChunker class├── vector_store.py         # FAISS management

│   ├── embeddings/├── ingestion/loader.py     # Paper ingestion

│   │   ├── __init__.py├── chunking/processor.py   # Text chunking

│   │   └── embedder.py         # EmbeddingGenerator class├── embeddings/embedder.py  # Embedding generation

│   ├── retrieval/├── retrieval/retriever.py  # Semantic search

│   │   ├── __init__.py└── generation/generator.py # Answer generation

│   │   └── retriever.py        # Retriever class```

│   └── generation/

│       ├── __init__.py## Dependencies

│       └── generator.py        # AnswerGenerator class

├── pyproject.toml- Python 3.11+

├── .env.example- MongoDB Atlas

└── README.md- FAISS

```- sentence-transformers

- pymongo

## Usage- nltk

- numpy

### 1. Ingest Papers

See `pyproject.toml` for full list.

```bash

python -m src.main ingest --query "machine learning" --max-results 10## See Also

```

- `QUICKSTART.md` - Quick start guide

### 2. Build FAISS Index- `STAGE1_COMPLETE.md` - Stage 1 details

- `FOLDER_STRUCTURE.md` - Directory structure

```bash
python -m src.main build-index
```

### 3. Query the System

```bash
python -m src.main query --query "What is the definition of machine learning?" --top-k 5
```

### 4. Check System Status

```bash
python -m src.main status
```

### 5. Reset System

```bash
python -m src.main reset
```

## Database Schema

### papers collection
```json
{
  "paper_id": "string",
  "title": "string",
  "abstract": "string",
  "year": "int",
  "citation_count": "int",
  "source": "string"
}
```

### chunks collection
```json
{
  "chunk_id": "string (UUID)",
  "paper_id": "string",
  "text": "string",
  "section": "abstract",
  "embedding_index": "int (FAISS row position)"
}
```

## Architecture

### Query Flow
```
User Query
    ↓
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
