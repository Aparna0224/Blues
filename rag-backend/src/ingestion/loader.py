"""Data ingestion from OpenAlex and Semantic Scholar APIs."""

import requests
import uuid
from typing import List, Dict, Any, Optional
from src.config import Config
from src.database import get_mongo_client


class PaperIngestor:
    """Ingest papers from OpenAlex or Semantic Scholar APIs."""
    
    def __init__(self, source: str = None):
        """
        Initialize paper ingestor.
        
        Args:
            source: API source ('openalex' or 'semantic_scholar'). 
                    Defaults to Config.DEFAULT_PAPER_SOURCE.
        """
        self.source = source or Config.DEFAULT_PAPER_SOURCE
        self.mongo = get_mongo_client()
        
        # OpenAlex settings
        self.openalex_base_url = Config.OPENALEX_BASE_URL
        self.openalex_api_key = Config.OPENALEX_API_KEY
        self.openalex_timeout = Config.OPENALEX_TIMEOUT
        
        # Semantic Scholar settings
        self.semantic_scholar_base_url = Config.SEMANTIC_SCHOLAR_BASE_URL
        self.semantic_scholar_api_key = Config.SEMANTIC_SCHOLAR_API_KEY
        self.semantic_scholar_timeout = Config.SEMANTIC_SCHOLAR_TIMEOUT
    
    def fetch_papers(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch papers from configured API source.
        
        Args:
            query: Search query (e.g., "machine learning")
            max_results: Maximum number of papers to fetch
            
        Returns:
            List of normalized paper objects
        """
        if self.source == "semantic_scholar":
            return self._fetch_from_semantic_scholar(query, max_results)
        else:
            return self._fetch_from_openalex(query, max_results)
    
    def _fetch_from_openalex(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch papers from OpenAlex API.
        
        Uses mailto for polite pool access (higher rate limits).
        
        Args:
            query: Search query
            max_results: Maximum papers to fetch
            
        Returns:
            List of normalized paper objects
        """
        try:
            url = f"{self.openalex_base_url}/works"
            params = {
                "search": query,
                "per_page": min(max_results, 50),
                # Note: sort parameter format changed - use 'publication_year:desc' or remove
            }
            
            # OpenAlex uses 'mailto' for polite pool access
            params["mailto"] = "aparna6024@gmail.com"
            print(f"✓ Using OpenAlex polite pool")
            
            headers = {
                "User-Agent": "RAG-Backend/0.1.0"
            }
            
            response = requests.get(
                url, 
                params=params, 
                headers=headers,
                timeout=self.openalex_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for work in data.get("results", []):
                paper = self._normalize_openalex_paper(work)
                if paper:
                    papers.append(paper)
            
            print(f"✓ Fetched {len(papers)} papers from OpenAlex")
            return papers
        
        except requests.RequestException as e:
            print(f"✗ Error fetching papers from OpenAlex: {e}")
            return []
    
    def _fetch_from_semantic_scholar(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch papers from Semantic Scholar API.
        
        Rate limit: 100 requests/5 minutes without API key.
        
        Args:
            query: Search query
            max_results: Maximum papers to fetch
            
        Returns:
            List of normalized paper objects
        """
        try:
            url = f"{self.semantic_scholar_base_url}/paper/search"
            params = {
                "query": query,
                "limit": min(max_results, 100),
                "fields": "paperId,title,abstract,year,citationCount"
            }
            
            headers = {
                "User-Agent": "RAG-Backend/0.1.0"
            }
            
            # Add API key if available
            if self.semantic_scholar_api_key:
                headers["x-api-key"] = self.semantic_scholar_api_key
                print(f"✓ Using Semantic Scholar API key")
            else:
                print(f"⚠ No Semantic Scholar API key - limited rate")
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.semantic_scholar_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for work in data.get("data", []):
                paper = self._normalize_semantic_scholar_paper(work)
                if paper:
                    papers.append(paper)
            
            print(f"✓ Fetched {len(papers)} papers from Semantic Scholar")
            return papers
        
        except requests.RequestException as e:
            print(f"✗ Error fetching papers from Semantic Scholar: {e}")
            return []
    
    def _normalize_openalex_paper(self, work: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize OpenAlex paper data."""
        try:
            # OpenAlex returns abstract as inverted index - convert to plain text
            abstract = None
            abstract_inverted_index = work.get("abstract_inverted_index")
            if abstract_inverted_index:
                abstract = self._convert_inverted_index_to_text(abstract_inverted_index)
            
            if not abstract:
                return None
            
            paper = {
                "paper_id": work.get("id", "").split("/")[-1],
                "title": work.get("title", "") or work.get("display_name", ""),
                "abstract": abstract,
                "year": work.get("publication_year", 0),
                "citation_count": work.get("cited_by_count", 0),
                "source": "openalex"
            }
            
            return paper
        except Exception as e:
            print(f"✗ Error normalizing OpenAlex paper: {e}")
            return None
    
    def _convert_inverted_index_to_text(self, inverted_index: Dict[str, List[int]]) -> str:
        """
        Convert OpenAlex abstract_inverted_index to plain text.
        
        OpenAlex stores abstracts as inverted indexes where each word maps to 
        its positions in the text. This function reconstructs the original text.
        
        Args:
            inverted_index: Dictionary mapping words to position lists
            
        Returns:
            Reconstructed plain text abstract
        """
        if not inverted_index:
            return ""
        
        # Create a list of (position, word) tuples
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        # Sort by position and join words
        word_positions.sort(key=lambda x: x[0])
        text = " ".join([word for _, word in word_positions])
        
        return text
    
    def _normalize_semantic_scholar_paper(self, work: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize Semantic Scholar paper data."""
        try:
            # Skip if no abstract
            abstract = work.get("abstract")
            if not abstract:
                return None
            
            paper = {
                "paper_id": work.get("paperId", ""),
                "title": work.get("title", ""),
                "abstract": abstract,
                "year": work.get("year", 0) or 0,
                "citation_count": work.get("citationCount", 0) or 0,
                "source": "semantic_scholar"
            }
            
            return paper
        except Exception as e:
            print(f"✗ Error normalizing Semantic Scholar paper: {e}")
            return None
    
    def insert_papers(self, papers: List[Dict[str, Any]]) -> int:
        """
        Insert papers into MongoDB.
        
        Args:
            papers: List of paper objects
            
        Returns:
            Number of papers inserted
        """
        if not papers:
            return 0
        
        try:
            papers_collection = self.mongo.get_papers_collection()
            result = papers_collection.insert_many(
                papers,
                ordered=False
            )
            print(f"✓ Inserted {len(result.inserted_ids)} papers into MongoDB")
            return len(result.inserted_ids)
        except Exception as e:
            # Handle duplicate key errors gracefully
            if "duplicate key" in str(e).lower():
                print(f"⚠ Some papers already exist in database")
            else:
                print(f"✗ Error inserting papers: {e}")
            return 0
    
    def ingest(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Full ingestion pipeline: fetch and insert papers.
        
        Args:
            query: Search query
            max_results: Maximum papers to ingest
            
        Returns:
            List of inserted papers
        """
        papers = self.fetch_papers(query, max_results)
        if papers:
            self.insert_papers(papers)
        return papers
