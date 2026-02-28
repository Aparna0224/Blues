"""Text chunking utilities with section detection."""

import re
import uuid
import nltk
from typing import List, Dict, Any, Tuple
from src.config import Config

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# ── Section heading patterns ──────────────────────────────────────

# Canonical section names (order matters — first match wins)
_SECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("introduction",  re.compile(r"^\s*\d*\.?\s*introduction", re.I)),
    ("background",    re.compile(r"^\s*\d*\.?\s*background", re.I)),
    ("literature_review", re.compile(r"^\s*\d*\.?\s*(literature\s+review|related\s+work|prior\s+work)", re.I)),
    ("methodology",   re.compile(r"^\s*\d*\.?\s*(method(s|ology)?|approach|experimental\s+(setup|design)|materials?\s+and\s+methods?)", re.I)),
    ("results",       re.compile(r"^\s*\d*\.?\s*(results?|findings|experimental\s+results?|evaluation)", re.I)),
    ("discussion",    re.compile(r"^\s*\d*\.?\s*(discussion|analysis|interpretation)", re.I)),
    ("conclusion",    re.compile(r"^\s*\d*\.?\s*(conclusion(s)?|summary|concluding\s+remarks?|final\s+remarks?)", re.I)),
    ("abstract",      re.compile(r"^\s*abstract", re.I)),
    ("references",    re.compile(r"^\s*\d*\.?\s*(references?|bibliography)", re.I)),
    ("acknowledgment", re.compile(r"^\s*\d*\.?\s*(acknowledg(e?ment|ments?))", re.I)),
    ("appendix",      re.compile(r"^\s*\d*\.?\s*(appendix|supplementary)", re.I)),
]

# Lines that look like section headings (short, possibly numbered/capitalised)
_HEADING_RE = re.compile(
    r"^(?:\d+\.?\s+)?[A-Z][A-Za-z\s&:,\-]{2,60}$"
)

# Sections we want to SKIP (don't create chunks from references etc.)
_SKIP_SECTIONS = {"references", "acknowledgment", "appendix"}


class TextChunker:
    """Split paper text into sentence-level chunks with section labels."""

    def __init__(self):
        self.min_sentences = Config.MIN_CHUNK_SENTENCES
        self.max_sentences = Config.MAX_CHUNK_SENTENCES

    # ── public API ────────────────────────────────────────────────

    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks of min–max sentences (no section info)."""
        try:
            sentences = nltk.sent_tokenize(text)
            if len(sentences) < self.min_sentences:
                return [text]
            chunks = []
            for i in range(0, len(sentences), self.min_sentences):
                chunk = " ".join(sentences[i:i + self.max_sentences])
                if chunk.strip():
                    chunks.append(chunk)
            return chunks
        except Exception as e:
            print(f"✗ Error chunking text: {e}")
            return [text]

    def create_chunks(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create chunks from papers with section detection.

        Uses full_text if available, otherwise falls back to abstract.
        Full-text is split into sections first, then each section is
        chunked independently so every chunk carries a section label.
        """
        chunks = []

        for paper in papers:
            full_text = paper.get("full_text")
            abstract = paper.get("abstract", "")

            if full_text and len(full_text) > len(abstract or ""):
                # ── Section-aware chunking for full text ──────────
                sections = self._detect_sections(full_text)
                order = 0
                for section_label, section_text in sections:
                    if section_label in _SKIP_SECTIONS:
                        continue
                    section_chunks = self.chunk_text(section_text)
                    for chunk_text in section_chunks:
                        chunks.append({
                            "chunk_id": str(uuid.uuid4()),
                            "paper_id": paper.get("paper_id"),
                            "text": chunk_text,
                            "section": section_label,
                            "embedding_index": None,
                            "chunk_order": order,
                        })
                        order += 1
            elif abstract:
                text_chunks = self.chunk_text(abstract)
                for idx, chunk_text in enumerate(text_chunks):
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "paper_id": paper.get("paper_id"),
                        "text": chunk_text,
                        "section": "abstract",
                        "embedding_index": None,
                        "chunk_order": idx,
                    })

        return chunks

    # ── section detection ─────────────────────────────────────────

    def _detect_sections(self, text: str) -> List[Tuple[str, str]]:
        """Split full-text into (section_label, section_text) pairs.

        Strategy:
          1. Split text into lines.
          2. Walk through lines; when a line matches a known heading
             pattern, start a new section.
          3. Lines that look like headings but don't match a known
             pattern are kept inside the current section (sub-headings).
          4. If no headings are detected at all, return the whole text
             as a single ``"body"`` section.
        """
        lines = text.split("\n")
        segments: List[Tuple[str, List[str]]] = []
        current_label = "body"
        current_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_lines.append("")
                continue

            # Check if this line matches a known section heading
            matched_label = self._match_heading(stripped)
            if matched_label is not None:
                # Save previous section
                if current_lines:
                    segments.append((current_label, current_lines))
                current_label = matched_label
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_lines:
            segments.append((current_label, current_lines))

        # Build (label, text) pairs, merging tiny segments into neighbours
        results: List[Tuple[str, str]] = []
        for label, seg_lines in segments:
            body = "\n".join(seg_lines).strip()
            if len(body) < 80 and results:
                # Too short to be a real section — merge into previous
                prev_label, prev_text = results[-1]
                results[-1] = (prev_label, prev_text + "\n\n" + body)
            elif body:
                results.append((label, body))

        if not results:
            return [("body", text)]
        return results

    @staticmethod
    def _match_heading(line: str) -> str | None:
        """Return canonical section label if *line* looks like a heading."""
        # Must look like a heading (short, title-case or numbered)
        if not _HEADING_RE.match(line) and not any(
            p.match(line) for _, p in _SECTION_PATTERNS
        ):
            return None

        for label, pattern in _SECTION_PATTERNS:
            if pattern.match(line):
                return label
        return None
