"""Base LLM interface for abstraction layer."""

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """
    Abstract base class for LLM implementations.
    
    All LLM providers (Ollama, Gemini, OpenAI) must implement this interface.
    This ensures the Planner Agent can work with any LLM backend.
    """
    
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The input prompt string
            
        Returns:
            The generated response string
        """
        raise NotImplementedError
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
