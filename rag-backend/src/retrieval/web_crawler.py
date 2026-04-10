# FILE: src/retrieval/web_crawler.py
"""
AcademicWebCrawler — Crawl4AI-based fallback retrieval for academic content.

Activation condition: only when DynamicRetriever API sources return < MIN_CHUNKS_THRESHOLD chunks.
Target sites: arxiv.org, ar5iv.org, pubmed.ncbi.nlm.nih.gov, semanticscholar.org, 
              scholar.google.com, research lab blogs.
"""

import asyncio
import hashlib
import httpx
from typing import List, Optional
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from src.config import Config

class AcademicWebCrawler:

    ACADEMIC_DOMAINS = [
        "arxiv.org", "ar5iv.org", "pubmed.ncbi.nlm.nih.gov",
        "semanticscholar.org", "aclanthology.org", "openreview.net",
        "dl.acm.org", "ieeexplore.ieee.org", "nature.com",
        "sciencedirect.com", "springer.com", "proceedings.mlr.press"
    ]

    async def crawl_url(self, url: str) -> Optional[dict]:
        """Crawl a single URL and return clean markdown text."""
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=150,         # Skip stub pages
                    excluded_tags=["nav", "footer", "header", "aside",
                                   "script", "style", ".references", ".citation"],
                    remove_overlay_elements=True,
                    bypass_cache=False,
                    timeout=20,
                )
                if result.success and result.markdown:
                    return {
                        "url": url,
                        "title": result.metadata.get("title", ""),
                        "content": result.markdown,
                        "source": "web_crawl"
                    }
        except Exception:
            pass
        return None

    async def crawl_multiple(self, urls: List[str]) -> List[dict]:
        """Crawl up to 8 URLs concurrently."""
        tasks = [self.crawl_url(u) for u in urls[:8]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict) and r]

    async def search_and_crawl(self, query: str, n: int = 5) -> List[dict]:
        """
        Use Brave Search API (or fallback to arXiv direct search) to find
        academic URLs for the query, then crawl them.
        """
        urls = await self._find_academic_urls(query, n)
        pages = await self.crawl_multiple(urls)
        return pages

    async def _find_academic_urls(self, query: str, n: int) -> List[str]:
        """Primary: Brave Search API. Fallback: arXiv search URL scrape."""
        # Try Brave Search first (requires BRAVE_API_KEY in config)
        if hasattr(Config, 'BRAVE_API_KEY') and Config.BRAVE_API_KEY:
            return await self._brave_search(query, n)
        # Fallback: arXiv search (always free, no key needed)
        return await self._arxiv_search(query, n)

    async def _brave_search(self, query: str, n: int) -> List[str]:
        domain_filter = " OR ".join(f"site:{d}" for d in self.ACADEMIC_DOMAINS[:6])
        search_query = f"{query} ({domain_filter})"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": Config.BRAVE_API_KEY
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": search_query, "count": n},
                    headers=headers
                )
            results = resp.json().get("web", {}).get("results", [])
            return [r["url"] for r in results if r.get("url")]
        except Exception:
            return []

    async def _arxiv_search(self, query: str, n: int) -> List[str]:
        """Direct arXiv API search — always available, no key needed."""
        import urllib.parse
        encoded = urllib.parse.quote(query)
        url = f"https://export.arxiv.org/api/query?search_query=all:{encoded}&max_results={n}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            soup = BeautifulSoup(resp.text, "xml")
            entries = soup.find_all("entry")
            # Use ar5iv.org for clean HTML versions instead of PDF
            urls = []
            for e in entries:
                arxiv_url = e.find("id").text.strip()
                arxiv_id = arxiv_url.split("/abs/")[-1]
                urls.append(f"https://ar5iv.org/abs/{arxiv_id}")
            return urls
        except Exception:
            return []
