"""Evidence extractor for sentence-level similarity scoring.

This module implements Stage 2 of the RAG pipeline:
- Splits chunk text into sentences using NLTK
- Computes sentence-level embeddings using SciBERT
- Selects the best matching sentence for each chunk
- Returns structured evidence with similarity scores
"""

import re
try:
    import nltk
except Exception:  # pragma: no cover - optional dependency fallback
    nltk = None
from typing import List, Dict, Any, Tuple
import numpy as np
from src.config import Config


class EvidenceExtractor:
    """Extract sentence-level evidence from retrieved chunks."""
    
    def __init__(self):
        """Initialize evidence extractor with NLTK sentence tokenizer."""
        self._use_nltk = nltk is not None
        if self._use_nltk:
            # Download NLTK data if not present
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                print("📥 Downloading NLTK punkt tokenizer...")
                nltk.download('punkt', quiet=True)

            try:
                nltk.data.find('tokenizers/punkt_tab')
            except LookupError:
                print("📥 Downloading NLTK punkt_tab tokenizer...")
                nltk.download('punkt_tab', quiet=True)
        
        self.embedder = None
        try:
            from src.embeddings.embedder import get_shared_embedder
            self.embedder = get_shared_embedder()
        except Exception:
            self.embedder = None
    
    # ── Junk-sentence detection patterns ─────────────────────────
    _CITATION_PATTERNS = [
        "vol.", "vol ", "no.", "doi:", "doi.org", "et al.", "et al,",
        "issn", "isbn", "arxiv:", "arxiv.", "pp.", "pp ", "pages ",
        "copyright", "©", "all rights reserved",
        "proceedings of", "conference on", "journal of",
        "international journal", "ieee", "acm", "springer",
        "published by", "accepted for", "submitted to",
    ]

    _STOP_WORDS = {
        "what", "how", "why", "when", "where", "which", "is", "are",
        "does", "do", "can", "the", "a", "an", "in", "of", "and",
        "or", "to", "for", "on", "with", "by", "from", "as", "at",
        "about", "into", "be", "this", "that", "it", "its", "their",
        "they", "them", "we", "our", "you", "your", "using", "used",
        "use", "uses", "benefits", "benefit",
    }

    _PROMPT_NOISE_PREFIXES = (
        "query:",
        "question:",
        "task:",
        "instruction:",
        "prompt:",
    )

    _HEADING_LINE_RE = re.compile(
        r"^\s*(abstract|introduction|background|related\s+work|method(?:s|ology)?|approach|framework|architecture|results?|evaluation|discussion|conclusion|future\s+work)\s*[:\-]?\s*$",
        re.IGNORECASE,
    )

    # Pre-compiled patterns for junk detection
    _AUTHOR_LIST_RE = re.compile(
        r'^[A-Z]\.\s+[A-Z][a-z]+,?\s+[A-Z]\.\s+[A-Z][a-z]+'
    )
    _NUMBERED_REF_RE = re.compile(r'^\[\d+\]\s+[A-Z]')

    @classmethod
    def _is_junk_sentence(cls, sentence: str) -> bool:
        """Return True if the sentence looks like a citation, header, or noise."""
        s = sentence.strip()
        words = s.split()

        # Too short to be meaningful content
        if len(words) < 3:
            return True

        # Author list pattern: "M. Leo, F. Tan, T. Miao"
        if cls._AUTHOR_LIST_RE.match(s):
            return True

        # Numbered reference: "[1] Smith, J. (2023). Title..."
        if cls._NUMBERED_REF_RE.match(s):
            return True

        # DOI lines
        if s.lower().startswith("https://doi") or s.lower().startswith("doi:"):
            return True

        # Lines that are mostly punctuation and numbers (bibliography entries)
        letters = sum(1 for c in s if c.isalpha())
        if letters > 0 and (len(s) - letters) / len(s) > 0.45 and len(words) < 12:
            return True

        # Require minimum meaningful word count for evidence sentences
        meaningful_words = [w for w in words if len(w) > 3]
        if len(meaningful_words) < 4:
            return True

        # Mostly uppercase (journal header / title block)
        alpha_chars = [c for c in s if c.isalpha()]
        if alpha_chars:
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_ratio > 0.6:
                return True

        # Mostly numeric / punctuation (table data, page numbers)
        alnum = [c for c in s if c.isalnum()]
        if alnum:
            digit_ratio = sum(1 for c in alnum if c.isdigit()) / len(alnum)
            if digit_ratio > 0.5:
                return True

        # Known citation / header patterns
        lower = s.lower()
        if any(pat in lower for pat in cls._CITATION_PATTERNS):
            return True

        # Prompt/template artifacts from scraped data
        if lower.startswith(cls._PROMPT_NOISE_PREFIXES):
            return True

        return False

    @classmethod
    def _clean_sentence(cls, sentence: str) -> str:
        """Normalize sentence text and strip citation/header artifacts."""
        if not sentence:
            return ""
        s = sentence.strip()
        s = re.sub(r"\[(\d+|\d+\s*[-,]\s*\d+)\]", "", s)
        s = re.sub(r"\(\s*\d{4}\s*\)", "", s)
        s = re.sub(r"\bet\s+al\.?[,]?\s*\(?\d{4}\)?", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip(" -:;,.\t")
        return s

    @classmethod
    def _is_broken_fragment(cls, sentence: str) -> bool:
        """Identify broken OCR fragments and non-readable lines."""
        s = (sentence or "").strip()
        if not s:
            return True
        if cls._HEADING_LINE_RE.match(s):
            return True
        if len(s.split()) < 5:
            return True
        if s.count(" ") <= 1 and len(s) > 20:
            return True
        if re.search(r"[\|_]{2,}", s):
            return True
        if re.search(r"\b(fig\.?|table|section)\s*\d+\b", s, flags=re.IGNORECASE):
            return True
        return False

    @classmethod
    def _tokenize_terms(cls, text: str) -> set[str]:
        if not text:
            return set()
        return {
            w.strip(".,;:()[]{}\"'`).?\n\t").lower()
            for w in text.split()
            if len(w.strip(".,;:()[]{}\"'`).?\n\t")) > 1
            and w.strip(".,;:()[]{}\"'`).?\n\t").lower() not in cls._STOP_WORDS
        }

    @classmethod
    def _has_query_term_overlap(cls, query: str, sentence: str, min_overlap: int) -> bool:
        if min_overlap <= 0:
            return True
        query_terms = cls._tokenize_terms(query)
        sentence_terms = cls._tokenize_terms(sentence)
        if not query_terms:
            return True
        return len(query_terms.intersection(sentence_terms)) >= min_overlap

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using NLTK.
        
        Args:
            text: Input text to split
            
        Returns:
            List of sentences
        """
        if not text or not text.strip():
            return []
        
        if self._use_nltk:
            sentences = nltk.sent_tokenize(text)
        else:
            clean_text = " ".join(text.replace("\n", " ").split())
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()]
            sentences = [s if s.endswith((".", "!", "?")) else f"{s}." for s in sentences]

        # Filter out very short sentences (likely noise)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        # Filter out question-like sentences when enabled
        if Config.FILTER_QUESTION_SENTENCES:
            sentences = [s for s in sentences if not s.strip().endswith("?")]
        
        # Filter out junk sentences (citations, headers, numeric noise)
        cleaned: List[str] = []
        for s in sentences:
            c = self._clean_sentence(s)
            if not c:
                continue
            if self._is_junk_sentence(c) or self._is_broken_fragment(c):
                continue
            cleaned.append(c)
        return cleaned

    def _score_sentences_in_order(self, query: str, sentences: List[str]) -> List[float]:
        """Return relevance scores preserving sentence order."""
        if not sentences:
            return []

        if self.embedder is None:
            q_terms = self._tokenize_terms(query)
            scores: List[float] = []
            for s in sentences:
                s_terms = self._tokenize_terms(s)
                if not q_terms or not s_terms:
                    scores.append(0.0)
                else:
                    scores.append(len(q_terms.intersection(s_terms)) / max(1, len(q_terms.union(s_terms))))
            return [float(x) for x in scores]

        query_embedding = self.embedder.embed_text(query)
        sentence_embeddings = self.embedder.embed_batch(sentences)
        return [float(np.dot(query_embedding, sentence_embeddings[i])) for i in range(len(sentences))]

    def select_best_paragraph(
        self,
        query: str,
        text: str,
        min_similarity: float = Config.EVIDENCE_MIN_SIMILARITY,
        min_sentences: int = 3,
        max_sentences: int = 5,
    ) -> Dict[str, Any]:
        """Select a clean, consecutive evidence paragraph (3–5 sentences)."""
        sentences = self.split_into_sentences(text)
        if not sentences:
            return {
                "best_paragraph": text[:220] if text else "",
                "best_score": 0.0,
                "start": 1,
                "end": 1,
                "all_sentences": [],
                "below_threshold": True,
            }

        scores = self._score_sentences_in_order(query, sentences)
        if not scores:
            return {
                "best_paragraph": sentences[0],
                "best_score": 0.0,
                "start": 1,
                "end": 1,
                "all_sentences": list(zip(sentences, [0.0] * len(sentences))),
                "below_threshold": True,
            }

        best = {"score": -1.0, "start": 0, "end": 1}
        max_len = min(max_sentences, len(sentences))
        min_len = min(min_sentences, max_len)
        for win_len in range(min_len, max_len + 1):
            for start in range(0, len(sentences) - win_len + 1):
                end = start + win_len
                window_scores = scores[start:end]
                avg_score = sum(window_scores) / max(1, len(window_scores))
                if avg_score > best["score"]:
                    best = {"score": avg_score, "start": start, "end": end}

        paragraph = " ".join(sentences[best["start"]:best["end"]]).strip()
        below_threshold = float(best["score"]) < float(min_similarity)
        return {
            "best_paragraph": paragraph,
            "best_score": float(best["score"]),
            "start": best["start"] + 1,
            "end": best["end"],
            "all_sentences": list(zip(sentences, scores)),
            "below_threshold": below_threshold,
        }
    
    def compute_sentence_similarity(
        self, 
        query: str, 
        sentences: List[str]
    ) -> List[Tuple[str, float]]:
        """
        Compute similarity between query and each sentence.
        
        Args:
            query: The query string
            sentences: List of sentences to compare
            
        Returns:
            List of (sentence, similarity_score) tuples sorted by score descending
        """
        if not sentences:
            return []

        if self.embedder is None:
            query_terms = self._tokenize_terms(query)
            scored = []
            for sentence in sentences:
                sent_terms = self._tokenize_terms(sentence)
                if not query_terms or not sent_terms:
                    score = 0.0
                else:
                    score = len(query_terms.intersection(sent_terms)) / max(1, len(query_terms.union(sent_terms)))
                scored.append((sentence, float(score)))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored
        
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)
        
        # Generate sentence embeddings
        sentence_embeddings = self.embedder.embed_batch(sentences)
        
        # Compute cosine similarities (embeddings are already normalized)
        similarities = []
        for i, sentence in enumerate(sentences):
            # Cosine similarity via dot product (normalized vectors)
            similarity = float(np.dot(query_embedding, sentence_embeddings[i]))
            similarities.append((sentence, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities
    
    def select_best_sentence(
    self, 
    query: str, 
    text: str, 
    min_similarity: float = Config.EVIDENCE_MIN_SIMILARITY
    ) -> Dict[str, Any]:
        """
        Select the most relevant sentence from text for a given query.
        
        Args:
            query: The query string
            text: The chunk text to analyze
            min_similarity: Minimum similarity threshold
            
        Returns:
            Dictionary with best sentence, score, and all sentence scores
        """
        paragraph = self.select_best_paragraph(
            query=query,
            text=text,
            min_similarity=min_similarity,
            min_sentences=3,
            max_sentences=5,
        )
        return {
            "best_sentence": paragraph.get("best_paragraph", ""),
            "best_score": float(paragraph.get("best_score", 0.0) or 0.0),
            "all_sentences": paragraph.get("all_sentences", []),
            "below_threshold": bool(paragraph.get("below_threshold", False)),
        }
    
    def extract_evidence_from_chunks(
        self, 
        query: str, 
        chunks: List[Dict[str, Any]],
        top_n_sentences: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Extract sentence-level evidence from retrieved chunks.
        
        This is the main method for Stage 2 evidence extraction.
        Embeds ALL sentences across ALL chunks in a single batch for efficiency,
        then finds the most relevant sentence(s) per chunk.
        
        Args:
            query: The query string
            chunks: List of retrieved chunk objects
            top_n_sentences: Number of top sentences to return per chunk
            
        Returns:
            List of chunks enhanced with evidence information:
            - evidence_sentence: The most relevant sentence
            - evidence_score: Similarity score for the evidence
            - sentence_scores: All sentence scores for the chunk
        """
        if not chunks:
            return []

        if self.embedder is None:
            enhanced_chunks = []
            for chunk in chunks:
                sel = self.select_best_paragraph(
                    query=query,
                    text=chunk.get("text", ""),
                    min_similarity=Config.EVIDENCE_MIN_SIMILARITY,
                    min_sentences=3,
                    max_sentences=5,
                )
                enhanced_chunks.append({
                    **chunk,
                    "evidence_sentence": sel.get("best_paragraph", ""),
                    "evidence_score": float(sel.get("best_score", 0.0) or 0.0),
                    "sentence_scores": sel.get("all_sentences", []),
                    "evidence_below_threshold": bool(sel.get("below_threshold", False)),
                })
            return enhanced_chunks

        # Step 1: Split all chunks into sentences and record boundaries
        all_sentences: List[str] = []
        chunk_boundaries: List[Tuple[int, int]] = []  # (start_idx, end_idx) per chunk

        for chunk in chunks:
            text = chunk.get("text", "")
            sentences = self.split_into_sentences(text)
            start = len(all_sentences)
            all_sentences.extend(sentences)
            end = len(all_sentences)
            chunk_boundaries.append((start, end))

        # Step 2: Batch-embed all sentences + query in one go
        query_embedding = self.embedder.embed_text(query)

        if all_sentences:
            sentence_embeddings = self.embedder.embed_batch(all_sentences)
        else:
            sentence_embeddings = np.array([])

        # Step 3: Score and assign best sentence per chunk
        enhanced_chunks = []
        min_similarity = Config.EVIDENCE_MIN_SIMILARITY

        for chunk_idx, chunk in enumerate(chunks):
            start, end = chunk_boundaries[chunk_idx]

            if start == end:
                # No valid sentences for this chunk
                text = chunk.get("text", "")
                enhanced_chunks.append({
                    **chunk,
                    "evidence_sentence": text[:200] if text else "",
                    "evidence_score": 0.0,
                    "evidence_below_threshold": True,
                })
                continue

            # Compute similarities for this chunk's sentences
            chunk_sents = all_sentences[start:end]
            chunk_embs = sentence_embeddings[start:end]
            scores = [float(np.dot(query_embedding, emb)) for emb in chunk_embs]

            # Select top 3–5 consecutive sentences by average relevance
            best = {"score": -1.0, "start": 0, "end": 1}
            max_len = min(5, len(chunk_sents))
            min_len = min(3, max_len)
            for win_len in range(min_len, max_len + 1):
                for w_start in range(0, len(chunk_sents) - win_len + 1):
                    w_end = w_start + win_len
                    avg_score = sum(scores[w_start:w_end]) / max(1, win_len)
                    if avg_score > best["score"]:
                        best = {"score": avg_score, "start": w_start, "end": w_end}

            best_sentence = " ".join(chunk_sents[best["start"]:best["end"]]).strip()
            best_score = float(best["score"])
            below_threshold = best_score < min_similarity

            enhanced_chunk = {
                **chunk,
                "evidence_sentence": best_sentence,
                "evidence_score": best_score,
                "evidence_below_threshold": below_threshold,
            }

            # Add top N sentences if requested
            if top_n_sentences > 1:
                indexed_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
                enhanced_chunk["top_sentences"] = [
                    {"sentence": chunk_sents[idx], "score": sc}
                    for idx, sc in indexed_scores[:top_n_sentences]
                ]

            enhanced_chunks.append(enhanced_chunk)
        
        return enhanced_chunks
    
    def format_evidence_output(self, enhanced_chunks: List[Dict[str, Any]]) -> str:
        """
        Format enhanced chunks as human-readable evidence output.
        
        Args:
            enhanced_chunks: Chunks with evidence information
            
        Returns:
            Formatted string for display
        """
        output = []
        output.append("=" * 78)
        output.append("SENTENCE-LEVEL EVIDENCE")
        output.append("=" * 78)
        
        for i, chunk in enumerate(enhanced_chunks, 1):
            # Handle both field naming conventions
            title = chunk.get("paper_title", chunk.get("title", "Unknown"))
            year = chunk.get("paper_year", chunk.get("year", "N/A"))
            chunk_sim = chunk.get("similarity_score", chunk.get("similarity", 0))
            evidence_sentence = chunk.get("evidence_sentence", "")
            evidence_score = chunk.get("evidence_score", 0)
            below_threshold = chunk.get("evidence_below_threshold", False)
            
            output.append(f"\n[{i}] {title} ({year})")
            output.append(f"    Chunk Similarity: {chunk_sim:.4f}")
            output.append(f"    Evidence Score: {evidence_score:.4f}")
            if below_threshold:
                output.append(f"    ⚠ Below similarity threshold")
            output.append(f"    Evidence: \"{evidence_sentence[:150]}...\"" 
                         if len(evidence_sentence) > 150 
                         else f"    Evidence: \"{evidence_sentence}\"")
        
        output.append("")
        return "\n".join(output)
