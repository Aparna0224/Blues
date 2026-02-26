"""Configuration management for RAG system."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration for RAG system."""
    
    # API Settings
    API_TITLE = "RAG System Backend"
    API_VERSION = "0.1.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # MongoDB Settings
    MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://user:password@cluster.mongodb.net/")
    MONGO_DB = os.getenv("MONGO_DB", "xai_rag")
    MONGO_PAPERS_COLLECTION = "papers"
    MONGO_CHUNKS_COLLECTION = "chunks"
    
    # Embedding Settings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "allenai/scibert_scivocab_uncased")
    EMBEDDING_DIMENSION = 768
    
    # FAISS Settings
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index.bin")
    FAISS_METRIC = "ip"  # Inner Product for cosine similarity
    
    # Retrieval Settings
    TOP_K = int(os.getenv("TOP_K", 5))
    
    # OpenAlex API Settings
    OPENALEX_BASE_URL = "https://api.openalex.org"
    OPENALEX_TIMEOUT = 10
    
    # Chunking Settings
    MIN_CHUNK_SENTENCES = 3
    MAX_CHUNK_SENTENCES = 5