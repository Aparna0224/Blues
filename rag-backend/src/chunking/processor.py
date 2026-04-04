"""Text chunking utilities for abstracts."""

import uuid
import re
import nltk
from typing import List, Dict, Any
from src.config import Config

# Download required NLTK data (punkt_tab for NLTK ≥ 3.9, punkt for older)
for _resource, _name in [('tokenizers/punkt_tab', 'punkt_tab'), ('tokenizers/punkt', 'punkt')]:
    try:
        nltk.data.find(_resource)
    except LookupError:
        nltk.download(_name, quiet=True)


class TextChunker:
    """Split abstracts into sentence-level chunks."""
    
    _SECTION_PATTERNS = [
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:abstract)\s*$', re.I), "abstract"),
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:introduction|background|motivation|overview)\s*$', re.I), "introduction"),
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:method|methods|methodology|approach|framework|system design|proposed|implementation)\s*$', re.I), "methodology"),
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:experiment|experiments|experimental|evaluation|results?|findings?|performance)\s*$', re.I), "results"),
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:discussion|analysis|limitations?)\s*$', re.I), "discussion"),
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:conclusion|conclusions?|future work|summary)\s*$', re.I), "conclusion"),
        (re.compile(r'^\s*(?:\d+\.?\s+)?(?:related work|literature review|prior work)\s*$', re.I), "related_work"),
    ]
    
    def __init__(self):
        self.min_sentences = Config.MIN_CHUNK_SENTENCES
        self.max_sentences = Config.MAX_CHUNK_SENTENCES

    @staticmethod
    def _build_tags(text: str, max_tags: int = 5) -> List[str]:
        """Extract simple keyword tags from text."""
        if not text:
            return []
        stop_words = {
            "what", "how", "why", "when", "where", "which", "is", "are",
            "does", "do", "can", "the", "a", "an", "in", "of", "and",
            "or", "to", "for", "on", "with", "by", "from", "as", "at",
            "about", "into", "be", "this", "that", "their", "its", "we",
            "our", "these", "those", "using", "use", "used", "via",
        }
        words = [
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in text.split()
            if w and len(w) > 2
        ]
        counts: Dict[str, int] = {}
        for w in words:
            if w in stop_words:
                continue
            counts[w] = counts.get(w, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [w for w, _ in ranked[:max_tags]]

    @staticmethod
    def _summarize_chunk(text: str) -> str:
        """Return a one-sentence summary of the chunk."""
        if not text:
            return ""
        try:
            sentences = nltk.sent_tokenize(text)
            return sentences[0].strip() if sentences else text[:160]
        except Exception:
            return text[:160]
    
    def _split_into_sections(self, text: str) -> List[tuple]:
        """Split full-text into (section_name, section_text) pairs based on section headers."""
        lines = text.split('\n')
        sections = []
        current_section = "introduction"
        current_lines = []
        
        for line in lines:
            stripped = line.strip()
            matched_section = None
            
            # Check if this line matches a section header
            for pattern, label in self._SECTION_PATTERNS:
                if pattern.match(stripped) and len(stripped) < 80:
                    matched_section = label
                    break
            
            if matched_section:
                # Save previous section if it has content
                if current_lines:
                    section_text = '\n'.join(current_lines).strip()
                    if section_text:
                        sections.append((current_section, section_text))
                current_section = matched_section
                current_lines = []
            else:
                current_lines.append(line)
        
        # Add the last section
        if current_lines:
            section_text = '\n'.join(current_lines).strip()
            if section_text:
                sections.append((current_section, section_text))
        
        return sections if sections else [("body", text)]
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks of 3-5 sentences.
        
        Args:
            text: Text to chunk (typically an abstract)
            
        Returns:
            List of text chunks
        """
        try:
            # Split into sentences
            sentences = nltk.sent_tokenize(text)
            
            if len(sentences) < self.min_sentences:
                # If fewer sentences than min, return as single chunk
                return [text]
            
            # Create chunks of min-max sentences
            chunks = []
            for i in range(0, len(sentences), self.min_sentences):
                chunk_sentences = sentences[i:i + self.max_sentences]
                chunk = " ".join(chunk_sentences)
                if chunk.strip():
                    chunks.append(chunk)
            
            return chunks
        
        except Exception as e:
            print(f"✗ Error chunking text: {e}")
            return [text]  # Return original text as fallback
    
    def create_chunks(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create chunks from papers.
        
        Uses full_text if available, otherwise falls back to abstract.
        For full_text, detects and labels actual section headers (intro, methodology, results, etc).
        
        Args:
            papers: List of paper objects with abstracts (and optionally full_text)
            
        Returns:
            List of chunk objects
        """
        chunks = []
        
        for paper in papers:
            full_text = paper.get("full_text")
            abstract = paper.get("abstract", "")
            title = paper.get("title", "")
            year = paper.get("year", "")
            source = paper.get("source", "")
            
            # Prefer full text when available, fall back to abstract
            if full_text and len(full_text) > len(abstract or ""):
                # Parse full text into actual sections
                text_sections = self._split_into_sections(full_text)
                tag_source = " ".join([title or "", abstract or ""]).strip()
                tags = self._build_tags(tag_source)
                category = tags[0] if tags else "general"
                
                for section_name, section_text in text_sections:
                    if not section_text.strip():
                        continue
                    section_chunks = self.chunk_text(section_text)
                    for idx, chunk_text_item in enumerate(section_chunks):
                        chunk = {
                            "chunk_id": str(uuid.uuid4()),
                            "paper_id": paper.get("paper_id"),
                            "text": chunk_text_item,
                            "section": section_name,  # real section, not "body"
                            "embedding_index": None,
                            "chunk_order": idx,
                            "metadata": {
                                "title": title,
                                "year": year,
                                "section": section_name,
                                "summary": self._summarize_chunk(chunk_text_item),
                                "tags": tags,
                                "category": category,
                                "source": source,
                            },
                        }
                        chunks.append(chunk)
            elif abstract:
                text_chunks = self.chunk_text(abstract)
                tag_source = " ".join([title or "", abstract or ""]).strip()
                tags = self._build_tags(tag_source)
                category = tags[0] if tags else "general"
                
                for idx, chunk_text in enumerate(text_chunks):
                    chunk = {
                        "chunk_id": str(uuid.uuid4()),
                        "paper_id": paper.get("paper_id"),
                        "text": chunk_text,
                        "section": "abstract",
                        "embedding_index": None,
                        "chunk_order": idx,
                        "metadata": {
                            "title": title,
                            "year": year,
                            "section": "abstract",
                            "summary": self._summarize_chunk(chunk_text),
                            "tags": tags,
                            "category": category,
                            "source": source,
                        },
                    }
                    chunks.append(chunk)
        
        return chunks
