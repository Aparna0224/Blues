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
    
    # Maximum characters to keep (very long papers → entire paper read)
    MAX_FULL_TEXT_LENGTH = 500_000  # Increased to read entire papers
    
    # Request timeout
    TIMEOUT = 30
    
    # Throttling to avoid rate limiting
    INTER_REQUEST_DELAY = 2  # seconds between requests
    
    # Headers to mimic a browser (some servers block plain requests)
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://scholar.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
    }

    def fetch_full_text(self, paper: Dict[str, Any]) -> Optional[str]:
        """
        Attempt to fetch full text for a paper. Enhanced to read entire papers.
        
        Tries multiple strategies in priority order:
        1. NCBI E-utilities FIRST for PMC articles (most reliable)
        2. Direct URL downloads (best_oa_pdf_url, oa_url, full_text_url) with throttling
        3. Publisher-specific alternative URLs (MDPI HTML, EuropePMC)
        4. Unpaywall API (DOI → working OA PDF link, with validation)
        5. Fallback to abstract
        
        Args:
            paper: Paper dict with URL fields
            
        Returns:
            Extracted full text string, or None if unavailable
        """
        title = paper.get("title", "Unknown")[:60]
        
        # ── Strategy 1: NCBI E-utilities FIRST (most reliable for PMC) ────────────
        pmcid = paper.get("pmcid") or ""
        if pmcid:
            print(f"     → Trying NCBI E-utilities first for {title}...")
            text = self._fetch_via_pmc(pmcid, title)
            if text:
                return text
        
        # ── Strategy 2: Direct URLs with throttling ────────────────────────────
        urls_to_try = []
        
        # Priority 2a: Direct PDF URL from best_oa_location
        best_pdf = paper.get("best_oa_pdf_url")
        if best_pdf:
            urls_to_try.append(("best_oa_pdf", best_pdf))
        
        # Priority 2b: OA URL (could be PDF or landing page)
        oa_url = paper.get("oa_url")
        if oa_url and oa_url != best_pdf:
            urls_to_try.append(("oa_url", oa_url))
        
        # Priority 2c: Generic full_text_url
        ft_url = paper.get("full_text_url")
        if ft_url and ft_url not in (best_pdf, oa_url):
            urls_to_try.append(("full_text_url", ft_url))
        
        # Try all direct URLs with throttling
        for source_name, url in urls_to_try:
            try:
                # Throttling to avoid rate limits (Fix #1)
                time.sleep(self.INTER_REQUEST_DELAY)
                
                text = self._download_and_extract(url)
                if text and len(text) >= self.MIN_FULL_TEXT_LENGTH:
                    print(f"     ✓ Full text extracted ({len(text)} chars) via {source_name}")
                    return text[:self.MAX_FULL_TEXT_LENGTH]
                
                # If PDF failed with 403, try MDPI HTML fallback (Fix #2)
                if "mdpi.com" in url.lower() and ".pdf" in url.lower():
                    print(f"     ⚠ PDF blocked, trying MDPI HTML version...")
                    html_url = url.replace(".pdf", "").split("?")[0]
                    text = self._download_and_extract(html_url)
                    if text and len(text) >= self.MIN_FULL_TEXT_LENGTH:
                        print(f"     ✓ Full text from MDPI HTML ({len(text)} chars)")
                        return text[:self.MAX_FULL_TEXT_LENGTH]
                        
            except Exception as e:
                print(f"     ⚠ {source_name} failed: {str(e)[:50]}")
                continue
        
        # ── Strategy 3: Alternative URLs for known publishers ───────────────────
        alt_urls = self._get_alternative_urls(paper, [u for _, u in urls_to_try])
        for source_name, url in alt_urls:
            try:
                time.sleep(self.INTER_REQUEST_DELAY)
                text = self._download_and_extract(url)
                if text and len(text) >= self.MIN_FULL_TEXT_LENGTH:
                    print(f"     ✓ Full text from {source_name} ({len(text)} chars)")
                    return text[:self.MAX_FULL_TEXT_LENGTH]
            except Exception as e:
                print(f"     ⚠ Alternative URL {source_name} failed: {str(e)[:50]}")
                continue
        
        # ── Strategy 4: Unpaywall API (with DOI validation) ────────────────────
        doi = paper.get("doi") or ""
        if doi and self._validate_doi(doi):  # Fix #3: Validate DOI first
            print(f"     → Trying Unpaywall API...")
            text = self._fetch_via_unpaywall(doi, title)
            if text:
                return text
        
        return None
    
    # ──────────────────────────────────────────────────────────────
    # Unpaywall API  (free, just needs an email)
    # ──────────────────────────────────────────────────────────────
    
    def _validate_doi(self, doi: str) -> bool:
        """
        Validate DOI format before API call (Fix #3).
        
        DOI format:
        - Standard: 10.xxxx/yyyy (numeric prefix, slash, publisher/article code)
        - May be URL: https://doi.org/10.xxxx/yyyy
        
        Args:
            doi: DOI string to validate
            
        Returns:
            True if valid format, False otherwise
        """
        if not doi:
            return False
        
        # Clean URL format to just the DOI
        doi_clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        
        # DOI format: 10.xxxx/yyyy (must start with "10.")
        if not doi_clean.startswith("10."):
            return False
        
        # Must have at least one slash
        if "/" not in doi_clean:
            return False
        
        # Basic length check
        if len(doi_clean) < 8 or len(doi_clean) > 256:
            return False
        
        return True

    def _fetch_via_unpaywall(self, doi: str, title: str = "") -> Optional[str]:
        """
        Use the Unpaywall API to find a working OA PDF link for a DOI.
        
        Unpaywall aggregates OA locations from repositories, publishers,
        and pre-print servers. Often returns links that work even when
        direct publisher URLs are blocked.
        
        Args:
            doi: The paper's DOI (e.g. "10.1234/example")
            title: Paper title for logging
            
        Returns:
            Extracted full text or None
        """
        doi_clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        if not doi_clean:
            return None
        
        api_url = f"https://api.unpaywall.org/v2/{doi_clean}?email=aparna6024@gmail.com"
        
        try:
            resp = requests.get(api_url, timeout=15)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            
            # Collect OA URLs from Unpaywall response (sorted by quality)
            oa_urls = []
            
            # Best OA location first
            best_oa = data.get("best_oa_location") or {}
            if best_oa.get("url_for_pdf"):
                oa_urls.append(("unpaywall_best_pdf", best_oa["url_for_pdf"]))
            if best_oa.get("url"):
                oa_urls.append(("unpaywall_best_landing", best_oa["url"]))
            
            # All OA locations (repositories, pre-print servers, etc.)
            for loc in (data.get("oa_locations") or []):
                pdf_url = loc.get("url_for_pdf")
                landing_url = loc.get("url")
                if pdf_url and ("unpaywall_best_pdf", pdf_url) not in oa_urls:
                    oa_urls.append(("unpaywall_repo_pdf", pdf_url))
                if landing_url and ("unpaywall_best_landing", landing_url) not in oa_urls:
                    oa_urls.append(("unpaywall_repo_landing", landing_url))
            
            # Try each Unpaywall URL
            for source_name, url in oa_urls:
                try:
                    text = self._download_and_extract(url)
                    if text and len(text) >= self.MIN_FULL_TEXT_LENGTH:
                        print(f"     ✓ Full text extracted ({len(text)} chars) via {source_name}")
                        return text[:self.MAX_FULL_TEXT_LENGTH]
                except Exception:
                    continue
            
        except Exception as e:
            print(f"     ⚠ Unpaywall API error: {e}")
        
        return None
    
    # ──────────────────────────────────────────────────────────────
    # NCBI E-utilities  (PMC full-text XML — no auth required)
    # ──────────────────────────────────────────────────────────────
    
    def _fetch_via_pmc(self, pmcid: str, title: str = "") -> Optional[str]:
        """
        Fetch full-text XML from PubMed Central using NCBI E-utilities.
        
        The efetch API returns structured XML that is never blocked (it's
        the official NCBI programmatic access endpoint).
        
        Args:
            pmcid: PubMed Central ID (e.g. "PMC12345678")
            title: Paper title for logging
            
        Returns:
            Extracted full text or None
        """
        # Normalize PMCID
        pmcid_clean = pmcid.strip()
        if not pmcid_clean.upper().startswith("PMC"):
            pmcid_clean = f"PMC{pmcid_clean}"
        
        efetch_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pmc&id={pmcid_clean}&rettype=full&retmode=xml"
            f"&tool=rag-backend&email=aparna6024@gmail.com"
        )
        
        try:
            resp = requests.get(efetch_url, timeout=30)
            if resp.status_code != 200:
                print(f"     ⚠ PMC efetch returned {resp.status_code} for {pmcid_clean}")
                return None
            
            text = self._extract_from_pmc_xml(resp.text)
            if text and len(text) >= self.MIN_FULL_TEXT_LENGTH:
                print(f"     ✓ Full text extracted ({len(text)} chars) via PMC efetch ({pmcid_clean})")
                return text[:self.MAX_FULL_TEXT_LENGTH]
            
        except Exception as e:
            print(f"     ⚠ PMC efetch error for {pmcid_clean}: {e}")
        
        return None
    
    def _extract_from_pmc_xml(self, xml_text: str) -> Optional[str]:
        """
        Extract readable text from PMC full-text XML (JATS format).
        
        Targets <body> section which contains the article content,
        extracting text from <p>, <sec>, <title> elements.
        
        Args:
            xml_text: Raw XML string from efetch
            
        Returns:
            Extracted text or None
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        try:
            soup = BeautifulSoup(xml_text, "html.parser")
            
            # Find the <body> element (contains article text in JATS XML)
            body = soup.find("body")
            if not body:
                return None
            
            # Extract paragraphs and section titles
            parts = []
            for elem in body.find_all(["sec", "p", "title"]):
                # Only grab leaf <p> and <title> elements, skip container <sec>
                if elem.name == "sec":
                    continue
                text = elem.get_text(separator=" ", strip=True)
                if text and len(text) > 15:
                    parts.append(text)
            
            if not parts:
                # Fallback: grab all text from body
                text = body.get_text(separator="\n", strip=True)
                return text if len(text) >= self.MIN_FULL_TEXT_LENGTH else None
            
            return "\n\n".join(parts)
            
        except Exception as e:
            print(f"     ⚠ PMC XML parsing error: {e}")
            return None
    
    def _get_alternative_urls(self, paper: Dict[str, Any], existing_urls: list) -> list:
        """
        Generate alternative download URLs for known publishers.
        
        Some publishers block direct PDF links but allow HTML access,
        or have alternative endpoints that work better.
        
        Args:
            paper: Paper dict
            existing_urls: URLs already in the try list
            
        Returns:
            List of (source_name, url) tuples
        """
        alternatives = []
        all_urls = " ".join(existing_urls)
        
        # MDPI: /pdf URLs often blocked; try the HTML article page instead
        if "mdpi.com" in all_urls:
            for url in existing_urls:
                if "mdpi.com" in url and "/pdf" in url:
                    # Convert PDF URL to HTML article URL
                    html_url = re.sub(r'/pdf(\?.*)?$', '', url)
                    if html_url not in existing_urls:
                        alternatives.append(("mdpi_html", html_url))
        
        # PubMed Central: try the /articles/PMCxxxxxxx/ format with trailing slash
        if "pmc.ncbi.nlm.nih.gov" in all_urls or "ncbi.nlm.nih.gov/pmc" in all_urls:
            for url in existing_urls:
                if "pmc" in url.lower():
                    # Try adding trailing slash
                    if not url.endswith("/"):
                        alternatives.append(("pmc_slash", url + "/"))
                    # Try europepmc as alternative
                    pmc_match = re.search(r'PMC(\d+)|articles/(\d+)', url)
                    if pmc_match:
                        pmc_id = pmc_match.group(1) or pmc_match.group(2)
                        euro_url = f"https://europepmc.org/article/PMC/PMC{pmc_id}"
                        if euro_url not in existing_urls:
                            alternatives.append(("europepmc", euro_url))
        
        # DOI-based Unpaywall and PMC E-utilities are handled separately
        # in fetch_full_text() as fallback strategies.
        
        return alternatives
    
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
