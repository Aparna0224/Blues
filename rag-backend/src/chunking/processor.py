"""Text chunking utilities for abstracts."""

import uuid
import nltk
from typing import List, Dict, Any
from src.config import Config

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')


class TextChunker:
    """Split abstracts into sentence-level chunks."""
    
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
        Marks each chunk's section as 'body' or 'abstract' accordingly.
        
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
                text_to_chunk = full_text
                section = "body"
            elif abstract:
                text_to_chunk = abstract
                section = "abstract"
            else:
                continue
            
            text_chunks = self.chunk_text(text_to_chunk)
            tag_source = " ".join([title or "", abstract or ""]).strip()
            tags = self._build_tags(tag_source)
            category = tags[0] if tags else "general"
            
            for idx, chunk_text in enumerate(text_chunks):
                chunk = {
                    "chunk_id": str(uuid.uuid4()),
                    "paper_id": paper.get("paper_id"),
                    "text": chunk_text,
                    "section": section,
                    "embedding_index": None,
                    "chunk_order": idx,
                    "metadata": {
                        "title": title,
                        "year": year,
                        "section": section,
                        "summary": self._summarize_chunk(chunk_text),
                        "tags": tags,
                        "category": category,
                        "source": source,
                    },
                }
                chunks.append(chunk)
        
        return chunks
