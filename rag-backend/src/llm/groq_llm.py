"""Groq LLM implementation using Groq Cloud API."""

import requests
from typing import Optional
from .base import BaseLLM
from src.config import Config


class GroqLLM(BaseLLM):
    """
    Groq LLM using Groq Cloud API.
    
    Groq provides extremely fast inference using their LPU hardware.
    Default model: llama3-8b-8192
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize GroqLLM.
        
        Args:
            api_key: Groq API key (default from Config.GROQ_API_KEY)
            model: Groq model name (default from Config.GROQ_MODEL)
            timeout: Request timeout in seconds (default from Config.GROQ_TIMEOUT)
        """
        self.api_key = api_key or Config.GROQ_API_KEY
        self.model = model or Config.GROQ_MODEL
        self.timeout = timeout or Config.GROQ_TIMEOUT
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY env variable.")
    
    def generate(self, prompt: str) -> str:
        """
        Generate response using Groq API.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated response string
            
        Raises:
            RuntimeError: On API errors or failed generation
            ConnectionError: When Groq API is unreachable
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": Config.LLM_TEMPERATURE,
                "max_tokens": 1024,
                "top_p": 0.8
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            elif response.status_code == 429:
                raise RuntimeError("Groq API rate limit exceeded. Please wait and retry.")
            else:
                raise RuntimeError(f"Groq API returned status {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            raise RuntimeError("Groq API request timed out")
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Could not connect to Groq API")
        except RuntimeError:
            raise  # re-raise our own RuntimeErrors
        except Exception as e:
            raise RuntimeError(f"Groq generation failed: {str(e)}")
    
    def __repr__(self) -> str:
        return f"GroqLLM(model={self.model})"
