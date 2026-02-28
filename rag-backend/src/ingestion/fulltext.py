"""Full-text extraction from open-access papers (PDF/HTML)."""

import io
import re
import time
import requests
from typing import Optional, Dict, Any


class FullTextFetcher:
    """
    Download and extract full text from open-access paper URLs.
    
    Supports:
    - PDF extraction via PyMuPDF (fitz)
    - HTML extraction via BeautifulSoup (fallback)
    
    Two-stage strategy:
    1. Try direct PDF link (best_oa_location.pdf_url or open_access.oa_url)
    2. Fallback to landing page HTML extraction
    """
    
    # Minimum characters for a "useful" full text (skip tiny extractions)
    MIN_FULL_TEXT_LENGTH = 500
    
    # Maximum characters to keep (very long papers → truncate)
    MAX_FULL_TEXT_LENGTH = 100_000
    
    # Request timeout
    TIMEOUT = 30
    
    # Headers to mimic a browser (some servers block plain requests)
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,text/html,application/xhtml+xml,*/*",
    }

    def fetch_full_text(self, paper: Dict[str, Any]) -> Optional[str]:
        """
        Attempt to fetch full text for a paper.
        
        Tries multiple URL sources in order of preference:
        1. best_oa_pdf_url (direct PDF link from best_oa_location)
        2. oa_url (open_access.oa_url — may be PDF or landing page)
        3. full_text_url (any other URL we stored)
        
        Args:
            paper: Paper dict with URL fields
            
        Returns:
            Extracted full text string, or None if unavailable
        """
        # Collect candidate URLs in priority order
        urls_to_try = []
        
        # Priority 1: Direct PDF URL from best_oa_location
        best_pdf = paper.get("best_oa_pdf_url")
        if best_pdf:
            urls_to_try.append(("best_oa_pdf", best_pdf))
        
        # Priority 2: OA URL (could be PDF or landing page)
        oa_url = paper.get("oa_url")
        if oa_url and oa_url != best_pdf:
            urls_to_try.append(("oa_url", oa_url))
        
        # Priority 3: Generic full_text_url
        ft_url = paper.get("full_text_url")
        if ft_url and ft_url not in (best_pdf, oa_url):
            urls_to_try.append(("full_text_url", ft_url))
        
        if not urls_to_try:
            return None
        
        title = paper.get("title", "Unknown")[:60]
        
        for source_name, url in urls_to_try:
            try:
                text = self._download_and_extract(url)
                if text and len(text) >= self.MIN_FULL_TEXT_LENGTH:
                    print(f"     ✓ Full text extracted ({len(text)} chars) via {source_name}")
                    return text[:self.MAX_FULL_TEXT_LENGTH]
            except Exception as e:
                print(f"     ⚠ {source_name} failed for '{title}': {e}")
                continue
        
        return None
    
    def _download_and_extract(self, url: str) -> Optional[str]:
        """
        Download a URL and extract text (PDF or HTML).
        
        Args:
            url: URL to download
            
        Returns:
            Extracted text or None
        """
        response = requests.get(
            url,
            headers=self.HEADERS,
            timeout=self.TIMEOUT,
            allow_redirects=True,
            stream=True
        )
        response.raise_for_status()
        
        content_type = response.headers.get("Content-Type", "").lower()
        
        # Check if it's a PDF
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return self._extract_from_pdf(response.content)
        
        # Otherwise try HTML
        if "html" in content_type or "xml" in content_type:
            return self._extract_from_html(response.text)
        
        # If content type is ambiguous, check the first bytes
        first_bytes = response.content[:5]
        if first_bytes == b"%PDF-":
            return self._extract_from_pdf(response.content)
        
        return None
    
    def _extract_from_pdf(self, pdf_bytes: bytes) -> Optional[str]:
        """
        Extract text from PDF bytes using PyMuPDF.
        
        Args:
            pdf_bytes: Raw PDF file bytes
            
        Returns:
            Extracted text or None
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("     ⚠ PyMuPDF (fitz) not installed. Run: uv add pymupdf")
            return None
        
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(page_text.strip())
            
            doc.close()
            
            if not text_parts:
                return None
            
            full_text = "\n\n".join(text_parts)
            
            # Clean up common PDF artifacts
            full_text = self._clean_pdf_text(full_text)
            
            return full_text if len(full_text) >= self.MIN_FULL_TEXT_LENGTH else None
            
        except Exception as e:
            print(f"     ⚠ PDF extraction error: {e}")
            return None
    
    def _extract_from_html(self, html: str) -> Optional[str]:
        """
        Extract article body text from HTML using BeautifulSoup.
        
        Args:
            html: Raw HTML string
            
        Returns:
            Extracted text or None
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("     ⚠ BeautifulSoup not installed. Run: uv add beautifulsoup4")
            return None
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove script, style, nav, footer, header elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "meta", "link"]):
                tag.decompose()
            
            # Try to find the article body using common selectors
            article_body = None
            selectors = [
                "article",
                ".article-body",
                ".paper-body",
                ".full-text",
                ".fulltext",
                "#article-body",
                ".content-body",
                "main",
                ".main-content",
                "[role='main']",
            ]
            
            for selector in selectors:
                article_body = soup.select_one(selector)
                if article_body and len(article_body.get_text(strip=True)) > self.MIN_FULL_TEXT_LENGTH:
                    break
                article_body = None
            
            # Fallback: just grab the body
            if not article_body:
                article_body = soup.find("body")
            
            if not article_body:
                return None
            
            # Get paragraphs for cleaner text
            paragraphs = article_body.find_all(["p", "section"])
            if paragraphs:
                text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
            else:
                text = article_body.get_text(separator="\n", strip=True)
            
            return text if len(text) >= self.MIN_FULL_TEXT_LENGTH else None
            
        except Exception as e:
            print(f"     ⚠ HTML extraction error: {e}")
            return None
    
    def _clean_pdf_text(self, text: str) -> str:
        """
        Clean common PDF extraction artifacts.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace / line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove page numbers (common patterns)
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        
        # Remove header/footer repetitions (short repeated lines)
        lines = text.split('\n')
        line_counts = {}
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) < 80:
                line_counts[stripped] = line_counts.get(stripped, 0) + 1
        
        # Remove lines that appear more than 3 times (likely headers/footers)
        repeated_lines = {line for line, count in line_counts.items() if count > 3}
        if repeated_lines:
            lines = [line for line in lines if line.strip() not in repeated_lines]
            text = '\n'.join(lines)
        
        # Remove hyphenation at line breaks (e.g., "con-\ntinue" → "continue")
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        
        # Collapse multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()
