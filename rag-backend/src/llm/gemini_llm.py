"""Gemini LLM implementation using Google Generative AI API."""

import requests
from typing import Optional
from .base import BaseLLM
from src.config import Config


class GeminiLLM(BaseLLM):
    """
    Google Gemini LLM using REST API.
    
    Uses the Gemini API for cloud-based inference.
    Default model: gemini-2.0-flash
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize GeminiLLM.
        
        Args:
            api_key: Google Gemini API key (default from Config.GEMINI_API_KEY)
            model: Gemini model name (default from Config.GEMINI_MODEL)
            timeout: Request timeout in seconds (default from Config.GEMINI_TIMEOUT)
        """
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model = model or Config.GEMINI_MODEL
        self.timeout = timeout or Config.GEMINI_TIMEOUT
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY env variable.")
    
    def generate(self, prompt: str) -> str:
        """
        Generate response using Gemini API.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated response string
        """
        try:
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": Config.LLM_TEMPERATURE,
                    "maxOutputTokens": 1024,
                    "topP": 0.8,
                    "topK": 40
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from Gemini response structure
            candidates = result.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            
            return ""
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                raise ValueError(f"Invalid request to Gemini API: {e.response.text}")
            elif e.response.status_code == 401:
                raise ValueError("Invalid Gemini API key")
            elif e.response.status_code == 429:
                raise RuntimeError("Gemini API rate limit exceeded")
            else:
                raise RuntimeError(f"Gemini API error: {e}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Gemini API request timed out after {self.timeout}s")
        except requests.RequestException as e:
            raise RuntimeError(f"Gemini API connection error: {e}")
    
    def is_available(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            # Simple test with minimal prompt
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": "Hello"}]}],
                "generationConfig": {"maxOutputTokens": 10}
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def __repr__(self) -> str:
        return f"GeminiLLM(model='{self.model}')"
