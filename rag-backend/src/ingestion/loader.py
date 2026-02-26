"""Data ingestion from OpenAlex API."""

import requests
import uuid
from typing import List, Dict, Any
from src.config import Config
from src.database import get_mongo_client

class PaperIngestor:
    """Ingest papers from OpenAlex API."""
    
    def __init__(self):
        self.base_url = Config.OPENALEX_BASE_URL
        self.timeout = Config.OPENALEX_TIMEOUT
        self.mongo = get_mongo_client()
    
    def fetch_papers(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch papers from OpenAlex API.
        
        Args:
            query: Search query (e.g., "machine learning")
            max_results: Maximum number of papers to fetch
            
        Returns:
            List of normalized paper objects
        """
        try:
            url = f"{self.base_url}/works"
            params = {
                "search": query,
                "per_page": min(max_results, 50),
                "sort": "-publication_year"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for work in data.get("results", []):
                paper = self._normalize_paper(work)
                if paper:
                    papers.append(paper)
            
            print(f"✓ Fetched {len(papers)} papers from OpenAlex")
            return papers
        
        except requests.RequestException as e:
            print(f"✗ Error fetching papers: {e}")
            return []
    
    def _normalize_paper(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize OpenAlex paper data."""
        try:
            # Skip if no abstract
            abstract = work.get("abstract")
            if not abstract:
                return None
            
            paper = {
                "paper_id": work.get("id", "").split("/")[-1],
                "title": work.get("title", ""),
                "abstract": abstract,
                "year": work.get("publication_year", 0),
                "citation_count": work.get("cited_by_count", 0),
                "source": "openalex"
            }
            
            return paper
        except Exception as e:
            print(f"✗ Error normalizing paper: {e}")
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
