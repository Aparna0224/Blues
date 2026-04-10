"""Data ingestion from OpenAlex, Semantic Scholar, and arXiv APIs."""

import requests
import time
import uuid
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from src.config import Config
from src.database import get_mongo_client


class PaperIngestor:
    """Ingest papers from OpenAlex, Semantic Scholar, and arXiv APIs."""
    
    def __init__(self, source: str = None):
        """
        Initialize paper ingestor.
        
        Args:
        source: API source ('openalex', 'semantic_scholar', 'arxiv', 'both', 'all').
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

        # arXiv settings
        self.arxiv_base_url = Config.ARXIV_BASE_URL
        self.arxiv_timeout = Config.ARXIV_TIMEOUT
    
    def fetch_papers(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch papers from configured API source.
        
        Args:
            query: Search query (e.g., "machine learning")
            max_results: Maximum number of papers to fetch
            
        Returns:
            List of normalized paper objects
        """
        source = (self.source or "").strip().lower()
        if source == "both":
            return self._fetch_from_both(query, max_results)
        elif source == "all":
            return self._fetch_from_all(query, max_results)
        elif source == "semantic_scholar":
            return self._fetch_from_semantic_scholar(query, max_results)
        elif source == "arxiv":
            return self._fetch_from_arxiv(query, max_results)
        else:
            return self._fetch_from_openalex(query, max_results)

    def _fetch_from_all(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Fetch papers from OpenAlex + Semantic Scholar + arXiv with deduplication."""
        per_source = max(max_results // 3, 4)

        print("📚 Fetching from OpenAlex + Semantic Scholar + arXiv...")

        openalex_papers = self._fetch_from_openalex(query, per_source)
        semantic_papers = self._fetch_from_semantic_scholar(query, per_source)
        arxiv_papers = self._fetch_from_arxiv(query, per_source)

        merged = self._deduplicate_papers(openalex_papers, semantic_papers)
        merged = self._deduplicate_papers(merged, arxiv_papers)

        print(
            "✓ Combined: "
            f"{len(merged)} unique papers "
            f"(OpenAlex: {len(openalex_papers)}, Semantic Scholar: {len(semantic_papers)}, arXiv: {len(arxiv_papers)})"
        )
        return merged[:max_results]
    
    def _fetch_from_both(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch papers from both OpenAlex and Semantic Scholar APIs.
        
        Combines results from both APIs with deduplication based on title similarity.
        Splits max_results between both APIs (half each).
        
        Args:
            query: Search query
            max_results: Maximum total papers to fetch
            
        Returns:
            List of normalized paper objects from both sources
        """
        per_source = max(max_results // 2, 5)  # At least 5 per source
        
        print(f"📚 Fetching from both OpenAlex and Semantic Scholar...")
        
        # Fetch from both sources
        openalex_papers = self._fetch_from_openalex(query, per_source)
        semantic_papers = self._fetch_from_semantic_scholar(query, per_source)
        
        # Combine and deduplicate
        all_papers = self._deduplicate_papers(openalex_papers, semantic_papers)
        
        print(f"✓ Combined: {len(all_papers)} unique papers (OpenAlex: {len(openalex_papers)}, Semantic Scholar: {len(semantic_papers)})")
        
        return all_papers[:max_results]
    
    def _deduplicate_papers(self, papers1: List[Dict[str, Any]], papers2: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate papers from two sources based on title similarity.
        
        Uses simple title normalization to detect duplicates.
        Prefers papers with longer abstracts when duplicates found.
        
        Args:
            papers1: First list of papers
            papers2: Second list of papers
            
        Returns:
            Deduplicated list of papers
        """
        def normalize_title(title: str) -> str:
            """Normalize title for comparison."""
            return title.lower().strip().replace("-", " ").replace(":", "")
        
        seen_titles = {}
        result = []
        
        # Add papers from first source
        for paper in papers1:
            norm_title = normalize_title(paper.get("title", ""))
            if norm_title and norm_title not in seen_titles:
                seen_titles[norm_title] = paper
                result.append(paper)
        
        # Add unique papers from second source
        for paper in papers2:
            norm_title = normalize_title(paper.get("title", ""))
            if norm_title and norm_title not in seen_titles:
                seen_titles[norm_title] = paper
                result.append(paper)
            elif norm_title in seen_titles:
                # If duplicate found, keep the one with longer abstract
                existing = seen_titles[norm_title]
                if len(paper.get("abstract", "")) > len(existing.get("abstract", "")):
                    # Replace with better version
                    idx = result.index(existing)
                    result[idx] = paper
                    seen_titles[norm_title] = paper
        
        return result
    
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
                # Only return open-access papers so we can actually download full text
                "filter": "open_access.is_oa:true",
            }
            
            # OpenAlex uses 'mailto' for polite pool access
            params["mailto"] = "aparna6024@gmail.com"
            print(f"✓ Using OpenAlex polite pool (OA-only filter)")
            
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
    
    def _fetch_from_semantic_scholar(self, query: str, max_results: int = 10, retries: int = 3) -> List[Dict[str, Any]]:
        """
        Fetch papers from Semantic Scholar API.
        
        Rate limit: 100 requests/5 minutes without API key.
        Includes retry logic with exponential backoff for rate limits.
        
        Args:
            query: Search query
            max_results: Maximum papers to fetch
            retries: Number of retry attempts for rate limit errors
            
        Returns:
            List of normalized paper objects
        """
        url = f"{self.semantic_scholar_base_url}/paper/search"
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "paperId,title,abstract,year,citationCount,openAccessPdf,url,externalIds"
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
        
        for attempt in range(retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.semantic_scholar_timeout
                )
                
                # Handle rate limit with retry
                if response.status_code == 429:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                    print(f"⏳ Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{retries})...")
                    time.sleep(wait_time)
                    continue
                
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
                if attempt < retries - 1 and "429" in str(e):
                    wait_time = 2 ** attempt
                    print(f"⏳ Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{retries})...")
                    time.sleep(wait_time)
                    continue
                print(f"✗ Error fetching papers from Semantic Scholar: {e}")
                return []
        
        print(f"✗ Semantic Scholar: Max retries exceeded")
        return []

    def _fetch_from_arxiv(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Fetch papers from arXiv API (Atom feed)."""
        try:
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": min(max_results, 100),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            headers = {"User-Agent": "RAG-Backend/0.1.0"}

            response = requests.get(
                self.arxiv_base_url,
                params=params,
                headers=headers,
                timeout=self.arxiv_timeout,
            )
            response.raise_for_status()

            root = ET.fromstring(response.text)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }

            papers: List[Dict[str, Any]] = []
            for entry in root.findall("atom:entry", ns):
                paper = self._normalize_arxiv_entry(entry, ns)
                if paper:
                    papers.append(paper)

            print(f"✓ Fetched {len(papers)} papers from arXiv")
            return papers
        except Exception as e:
            print(f"✗ Error fetching papers from arXiv: {e}")
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
            
            # Extract open-access / full-text URLs
            open_access = work.get("open_access") or {}
            oa_url = open_access.get("oa_url")          # best OA URL (may be PDF)
            is_oa = open_access.get("is_oa", False)
            
            # best_oa_location has a direct pdf_url when available
            best_oa = work.get("best_oa_location") or {}
            best_oa_pdf_url = best_oa.get("pdf_url")    # direct PDF link
            best_oa_landing = best_oa.get("landing_page_url")
            
            # has_content tells us if OpenAlex cached the full text
            has_content = work.get("has_content") or {}
            content_url = work.get("content_url")       # OpenAlex content API
            
            # Build a prioritized full_text_url
            full_text_url = best_oa_pdf_url or oa_url or best_oa_landing

            # Also try locations list for PDF URLs
            if not full_text_url:
                for loc in (work.get("locations") or []):
                    if loc.get("pdf_url"):
                        full_text_url = loc["pdf_url"]
                        break

            # Extract DOI (needed for Unpaywall fallback)
            doi_raw = work.get("doi") or work.get("ids", {}).get("doi") or ""
            doi = doi_raw.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()

            # Extract PubMed Central ID if available (needed for NCBI E-utilities)
            ids = work.get("ids") or {}
            pmcid = ""
            pmid = ""
            openalex_id = work.get("id", "")
            if ids.get("pmcid"):
                pmcid = str(ids["pmcid"]).replace("https://www.ncbi.nlm.nih.gov/pmc/articles/", "")
            if ids.get("pmid"):
                pmid = str(ids["pmid"]).replace("https://pubmed.ncbi.nlm.nih.gov/", "")

            paper = {
                "paper_id": openalex_id.split("/")[-1],
                "title": work.get("title", "") or work.get("display_name", ""),
                "abstract": abstract,
                "year": work.get("publication_year", 0),
                "citation_count": work.get("cited_by_count", 0),
                "source": "openalex",
                "is_oa": is_oa,
                "doi": doi,
                "pmcid": pmcid,
                "pmid": pmid,
                "full_text_url": full_text_url,
                "best_oa_pdf_url": best_oa_pdf_url,
                "oa_url": oa_url,
                "content_url": content_url,
                "has_content_pdf": has_content.get("pdf", False),
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
            # Accept papers with or without abstract
            abstract = work.get("abstract") or ""

            # Skip if no title
            title = work.get("title", "").strip()
            if not title:
                return None

            # Open access PDF URL
            oap = work.get("openAccessPdf") or {}
            best_oa_pdf_url = oap.get("url") if oap else None
            
            # Fallback to general paper URL
            oa_url = work.get("url")
            full_text_url = best_oa_pdf_url or oa_url

            # Extract external IDs (DOI, PMCID, etc.)
            ext_ids = work.get("externalIds") or {}
            doi = ext_ids.get("DOI", "") or ""
            pmcid = ext_ids.get("PMCID", "") or ""
            pmid = str(ext_ids.get("PubMed", "")) if ext_ids.get("PubMed") else ""

            paper = {
                "paper_id": work.get("paperId", ""),
                "title": title,
                "abstract": abstract,
                "year": work.get("year", 0) or 0,
                "citation_count": work.get("citationCount", 0) or 0,
                "source": "semantic_scholar",
                "is_oa": bool(best_oa_pdf_url),
                "doi": doi,
                "pmcid": pmcid,
                "pmid": pmid,
                "full_text_url": full_text_url,
                "best_oa_pdf_url": best_oa_pdf_url,
                "oa_url": oa_url,
            }
            
            return paper
        except Exception as e:
            print(f"✗ Error normalizing Semantic Scholar paper: {e}")
            return None

    def _normalize_arxiv_entry(self, entry: ET.Element, ns: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Normalize arXiv Atom entry into the common paper schema."""
        try:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            abstract = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
            if not title or not abstract:
                return None

            raw_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            paper_id = raw_id.split("/")[-1].replace("v", "_") if raw_id else str(uuid.uuid4())

            published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
            year = 0
            if len(published) >= 4 and published[:4].isdigit():
                year = int(published[:4])

            doi = (entry.findtext("arxiv:doi", default="", namespaces=ns) or "").strip()

            pdf_url = ""
            landing_url = raw_id
            for link in entry.findall("atom:link", ns):
                title_attr = (link.attrib.get("title") or "").lower()
                href = link.attrib.get("href") or ""
                typ = (link.attrib.get("type") or "").lower()
                if title_attr == "pdf" or typ == "application/pdf":
                    pdf_url = href
                if link.attrib.get("rel") == "alternate" and href:
                    landing_url = href

            full_text_url = pdf_url or landing_url

            return {
                "paper_id": f"arxiv_{paper_id}",
                "title": title,
                "abstract": abstract,
                "year": year,
                "citation_count": 0,
                "source": "arxiv",
                "is_oa": True,
                "doi": doi,
                "pmcid": "",
                "pmid": "",
                "full_text_url": full_text_url,
                "best_oa_pdf_url": pdf_url,
                "oa_url": landing_url,
            }
        except Exception as e:
            print(f"✗ Error normalizing arXiv paper: {e}")
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
