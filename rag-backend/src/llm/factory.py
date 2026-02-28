"""LLM factory for creating LLM instances based on configuration."""

from typing import Optional
from .base import BaseLLM
from .local import LocalLLM
from .gemini_llm import GeminiLLM
from .groq_llm import GroqLLM
from src.config import Config


def get_llm(provider: Optional[str] = None) -> BaseLLM:
    """
    Factory function to create LLM instance based on environment configuration.
    
    Configuration from src.config.Config:
        LLM_PROVIDER: "local" (Ollama), "gemini" (Google Gemini), or "groq" (Groq Cloud)
        OLLAMA_MODEL: Model name for Ollama (default: llama3:8b-instruct)
        OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
        GEMINI_API_KEY: Google Gemini API key
        GEMINI_MODEL: Gemini model name (default: gemini-2.0-flash)
        GROQ_API_KEY: Groq Cloud API key
        GROQ_MODEL: Groq model name (default: llama3-8b-8192)
    
    Args:
        provider: Override LLM_PROVIDER config (optional)
        
    Returns:
        BaseLLM instance (LocalLLM, GeminiLLM, or GroqLLM)
        
    Raises:
        ValueError: If provider is invalid or required config is missing
    """
    llm_provider = provider or Config.LLM_PROVIDER
    
    if llm_provider == "local":
        llm = LocalLLM()
        print(f"✓ Using LocalLLM: {Config.OLLAMA_MODEL}")
        return llm
    
    elif llm_provider == "gemini":
        if not Config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for Gemini provider"
            )
        
        llm = GeminiLLM()
        print(f"✓ Using GeminiLLM: {Config.GEMINI_MODEL}")
        return llm
    
    elif llm_provider == "groq":
        if not Config.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY environment variable is required for Groq provider"
            )
        
        llm = GroqLLM()
        print(f"✓ Using GroqLLM: {Config.GROQ_MODEL}")
        return llm
    
    else:
        raise ValueError(
            f"Invalid LLM_PROVIDER: '{llm_provider}'. "
            "Supported providers: 'local' (Ollama), 'gemini' (Google Gemini), 'groq' (Groq Cloud)"
        )
