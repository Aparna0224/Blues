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
    RETRIEVAL_MIN_SIMILARITY = float(os.getenv("RETRIEVAL_MIN_SIMILARITY", "0.50"))
    DYNAMIC_ABSTRACT_MIN_SIMILARITY = float(os.getenv("DYNAMIC_ABSTRACT_MIN_SIMILARITY", "0.45"))
    SUBQUESTION_ASSIGN_THRESHOLD = float(os.getenv("SUBQUESTION_ASSIGN_THRESHOLD", "0.45"))
    EVIDENCE_MIN_SIMILARITY = float(os.getenv("EVIDENCE_MIN_SIMILARITY", "0.55"))
    EVIDENCE_KEYWORD_MIN_OVERLAP = int(os.getenv("EVIDENCE_KEYWORD_MIN_OVERLAP", "1"))
    MIN_UNIQUE_PAPERS_FOR_CLAIMS = int(os.getenv("MIN_UNIQUE_PAPERS_FOR_CLAIMS", "2"))
    KEYWORD_MIN_OVERLAP = int(os.getenv("KEYWORD_MIN_OVERLAP", "2"))
    FILTER_QUESTION_SENTENCES = os.getenv("FILTER_QUESTION_SENTENCES", "True").lower() == "true"
    ENABLE_DOMAIN_KEYWORD_GATE = os.getenv("ENABLE_DOMAIN_KEYWORD_GATE", "False").lower() == "true"
    DOMAIN_KEYWORD_MIN_OVERLAP = int(os.getenv("DOMAIN_KEYWORD_MIN_OVERLAP", "1"))
    DOMAIN_KEYWORDS = [
        term.strip().lower()
        for term in os.getenv(
            "DOMAIN_KEYWORDS",
            "rag,retrieval,augmentation,context,grounding,assistant,research,query,documents",
        ).split(",")
        if term.strip()
    ]
    
    # Hybrid Retrieval Settings (BM25 + Semantic via RRF)
    HYBRID_RETRIEVAL_ENABLED = os.getenv("HYBRID_RETRIEVAL_ENABLED", "True").lower() == "true"
    RRF_K = int(os.getenv("RRF_K", "60"))
    BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "0.4"))
    SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", "0.6"))
    BM25_TOP_K = int(os.getenv("BM25_TOP_K", "20"))
    SOFT_FILTER_KEYWORD_PENALTY = float(os.getenv("SOFT_FILTER_KEYWORD_PENALTY", "0.85"))
    SOFT_FILTER_DOMAIN_PENALTY = float(os.getenv("SOFT_FILTER_DOMAIN_PENALTY", "0.85"))
    SOFT_FILTER_LOW_SEMANTIC_PENALTY = float(os.getenv("SOFT_FILTER_LOW_SEMANTIC_PENALTY", "0.7"))
    SOFT_FILTER_LOW_SEMANTIC_THRESHOLD = float(os.getenv("SOFT_FILTER_LOW_SEMANTIC_THRESHOLD", "0.35"))
    MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "0.005"))
    
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
    MIN_CHUNK_SENTENCES = int(os.getenv("MIN_CHUNK_SENTENCES", "8"))
    MAX_CHUNK_SENTENCES = int(os.getenv("MAX_CHUNK_SENTENCES", "12"))
    
    # LLM Settings (Stage 3)
    # LLM_PROVIDER: "local" for Ollama, "gemini" for Google Gemini API, "groq" for Groq Cloud
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local")
    
    # Ollama (Local LLM) Settings
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    
    # Google Gemini API Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))
    
    # Groq Cloud API Settings (Fast inference with LPU)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "30"))
    
    # LLM Generation Settings
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))