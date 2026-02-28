"""Local LLM implementation using Ollama."""

import requests
from typing import Optional
from .base import BaseLLM
from src.config import Config


class LocalLLM(BaseLLM):
    """
    Local LLM using Ollama HTTP API.
    
    Ollama must be running locally on the specified port.
    Default model: llama3:8b-instruct
    
    API endpoint: POST http://localhost:11434/api/generate
    """
    
    def __init__(
        self, 
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize LocalLLM.
        
        Args:
            model: Ollama model name (default from Config.OLLAMA_MODEL)
            base_url: Ollama server URL (default from Config.OLLAMA_BASE_URL)
            timeout: Request timeout in seconds (default from Config.OLLAMA_TIMEOUT)
        """
        self.model = model or Config.OLLAMA_MODEL
        self.base_url = base_url or Config.OLLAMA_BASE_URL
        self.timeout = timeout or Config.OLLAMA_TIMEOUT
        self.api_url = f"{self.base_url}/api/generate"
    
    def generate(self, prompt: str) -> str:
        """
        Generate response using Ollama.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated response string
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": Config.LLM_TEMPERATURE,
                    "num_predict": 1024   # Max tokens
                }
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
            
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: 'ollama serve'"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s. "
                "Try increasing timeout or using a smaller model."
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama API error: {e}")
    
    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return self.model in model_names or any(
                    self.model.split(":")[0] in name for name in model_names
                )
            return False
        except:
            return False
    
    def __repr__(self) -> str:
        return f"LocalLLM(model='{self.model}', base_url='{self.base_url}')"
