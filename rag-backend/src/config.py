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
    # Rate: 100k credits/day with key, 100 credits/day without
    # Cost: list request = 10 credits, singleton = 1 credit
    OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
    OPENALEX_BASE_URL = os.getenv("OPENALEX_BASE_URL", "https://api.openalex.org")
    OPENALEX_TIMEOUT = 30
    
    # Semantic Scholar API Settings
    # Rate: 100 requests/5 minutes without key
    SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    SEMANTIC_SCHOLAR_BASE_URL = os.getenv("SEMANTIC_SCHOLAR_BASE_URL", "https://api.semanticscholar.org/graph/v1")
    SEMANTIC_SCHOLAR_TIMEOUT = 30
    
    # Default Paper Source
    DEFAULT_PAPER_SOURCE = os.getenv("DEFAULT_PAPER_SOURCE", "openalex")
    
    # Chunking Settings
    MIN_CHUNK_SENTENCES = 3
    MAX_CHUNK_SENTENCES = 5
    
    # LLM Settings (Stage 3)
    # LLM_PROVIDER: "local" for Ollama, "gemini" for Google Gemini API
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local")
    
    # Ollama (Local LLM) Settings
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    
    # Google Gemini API Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))
    
    # LLM Generation Settings
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))