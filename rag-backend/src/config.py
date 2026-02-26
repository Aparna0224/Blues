import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_TITLE = "RAG System Backend"
    API_VERSION = "0.1.0"
    DEBUG = os.getenv("DEBUG", False)
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rag.db")
    
    # Embeddings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    
    # LLM
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
