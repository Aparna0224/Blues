"""Answer generation with citations."""

import re
from typing import List, Dict, Any, Optional
import numpy as np
from src.config import Config
from src.comparison.conflict_detector import ConflictDetector


class AnswerGenerator:
    """Generate answers from retrieved chunks with proper citations."""

    SECTION_MAP = {
        "introduction": ["introduction", "background", "abstract"],
        "methodology": ["method", "methods", "methodology", "approach", "body"],
        "results": ["results", "experiments", "evaluation", "findings"],
        "discussion": ["discussion", "analysis"],
        "conclusion": ["conclusion"],
    }
    TOP_CHUNKS_PER_SECTION = 2
    MAX_SECTIONS_PER_PAPER = 3
    PARAGRAPH_MIN_SENTENCES = 3
    PARAGRAPH_MAX_SENTENCES = 5
    SUBQUERY_HARD_GATE_THRESHOLD = 0.60
    SECTION_PREFERRED_BOOST = 1.2
    CONFIDENCE_W1 = 0.45
    CONFIDENCE_W2 = 0.35
    CONFIDENCE_W3 = 0.20
    
    def __init__(self):
        pass

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        if not text:
            return []
        clean = " ".join(text.replace("\n", " ").split())
        parts = re.split(r"(?<=[.!?])\s+", clean)
        return [p.strip() for p in parts if p.strip()]

    def _build_claim_snippet(
        self,
        text: str,
        evidence_sentence: str,
        max_sentences: int = 3,
    ) -> str:
        """Build a multi-line claim snippet centered on the evidence sentence."""
        sentences = self._split_sentences(text)
        if not sentences:
            return ""

        ev = " ".join((evidence_sentence or "").split()).strip()
        target_idx = -1
        if ev:
            ev_lower = ev.lower()
            for idx, sentence in enumerate(sentences):
                s_lower = sentence.lower()
                if ev_lower in s_lower or s_lower in ev_lower:
                    target_idx = idx
                    break

        if target_idx < 0:
            snippet_sents = sentences[:max_sentences]
        else:
            half = max(0, (max_sentences - 1) // 2)
            start = max(0, target_idx - half)
            end = min(len(sentences), start + max_sentences)
            start = max(0, end - max_sentences)
            snippet_sents = sentences[start:end]

        return "\n".join(snippet_sents)

    @staticmethod
    def _clean_sentence(sentence: str) -> str:
        """Remove noisy citation/header artifacts from a sentence."""
        if not sentence:
            return ""
        s = sentence.strip()
        s = re.sub(r"\bet\s+al\.?[,]?\s*\(?\d{4}\)?", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\[(\d+|\d+\s*[-,]\s*\d+)\]", "", s)
        s = re.sub(r"\(\s*\d{4}\s*\)", "", s)
        s = re.sub(r"^(abstract|introduction|background|methods?|methodology|results?|discussion|conclusion)\s*[:\-]\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip(" -:;,")
        if s and s[0].islower():
            s = s[0].upper() + s[1:]
        return s

    @staticmethod
    def _is_noise_sentence(sentence: str) -> bool:
        if not sentence:
            return True
        s = sentence.strip()
        if len(s.split()) < 6:
            return True
        lower = s.lower()
        if lower.endswith(":"):
            return True
        if any(p in lower for p in ["copyright", "all rights reserved", "doi:", "arxiv:"]):
            return True
        return False

    def _build_clean_paragraph(
        self,
        text: str,
        evidence_sentence: str,
        min_sentences: int | None = None,
        max_sentences: int | None = None,
    ) -> tuple[str, int, int]:
        """Build clean readable paragraph span and return (text, start, end)."""
        min_s = min_sentences or self.PARAGRAPH_MIN_SENTENCES
        max_s = max_sentences or self.PARAGRAPH_MAX_SENTENCES

        raw_sentences = self._split_sentences(text)
        cleaned = [self._clean_sentence(s) for s in raw_sentences]
        cleaned = [s for s in cleaned if s and not self._is_noise_sentence(s)]
        if not cleaned:
            return "", 1, 1

        ev = " ".join((evidence_sentence or "").split()).strip().lower()
        target_idx = 0
        if ev:
            for idx, sent in enumerate(cleaned):
                low = sent.lower()
                if ev in low or low in ev:
                    target_idx = idx
                    break

        desired = max(min_s, min(max_s, 4))
        half = desired // 2
        start = max(0, target_idx - half)
        end = min(len(cleaned), start + desired)
        start = max(0, end - desired)

        while (end - start) < min_s and end < len(cleaned):
            end += 1
        while (end - start) < min_s and start > 0:
            start -= 1

        paragraph = " ".join(cleaned[start:end]).strip()
        if not self._is_coherent_window(cleaned[start:end]):
            window = self._best_contiguous_window(cleaned, min_s=min_s, max_s=max_s)
            paragraph = " ".join(window["sentences"]).strip()
            return paragraph, window["start"] + 1, window["end"]

        return paragraph, start + 1, end

    @staticmethod
    def _is_coherent_window(sentences: List[str]) -> bool:
        """Heuristic coherence check for sentence windows."""
        if len(sentences) <= 1:
            return True
        stop = {
            "the", "and", "for", "with", "this", "that", "from", "into", "using",
            "are", "was", "were", "has", "have", "had", "into", "over", "under",
        }

        def terms(s: str) -> set[str]:
            return {
                w.strip(".,;:()[]{}\"'`").lower()
                for w in s.split()
                if len(w.strip(".,;:()[]{}\"'`")) > 2 and w.strip(".,;:()[]{}\"'`").lower() not in stop
            }

        overlaps = []
        for i in range(len(sentences) - 1):
            a = terms(sentences[i])
            b = terms(sentences[i + 1])
            if not a or not b:
                overlaps.append(0.0)
                continue
            overlaps.append(len(a.intersection(b)) / max(1, len(a.union(b))))

        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0
        return avg_overlap >= 0.05

    def _best_contiguous_window(
        self,
        sentences: List[str],
        min_s: int,
        max_s: int,
    ) -> Dict[str, Any]:
        """Fallback window chooser maximizing internal lexical coherence."""
        if not sentences:
            return {"sentences": [], "start": 0, "end": 0}

        best = {"score": -1.0, "sentences": sentences[:min_s], "start": 0, "end": min(len(sentences), min_s)}
        max_len = min(max_s, len(sentences))
        for win_len in range(min_s, max_len + 1):
            for start in range(0, len(sentences) - win_len + 1):
                end = start + win_len
                window = sentences[start:end]
                score = 1.0 if self._is_coherent_window(window) else 0.0
                if score > best["score"]:
                    best = {"score": score, "sentences": window, "start": start, "end": end}
        return best

    @staticmethod
    def _confidence_band(score: float) -> str:
        if score >= 0.75:
            return "High"
        if score >= 0.60:
            return "Medium"
        return "Low"

    @staticmethod
    def _section_preferences(sub_question: str) -> set[str]:
        sq = (sub_question or "").lower()
        if any(k in sq for k in ["method", "approach", "how"]):
            return {"Methodology", "Introduction"}
        if any(k in sq for k in ["result", "performance", "effective", "accuracy"]):
            return {"Results", "Discussion"}
        if any(k in sq for k in ["challenge", "limitation", "risk", "issue"]):
            return {"Discussion", "Conclusion"}
        return {"Introduction", "Methodology", "Results", "Discussion", "Conclusion", "unknown"}

    @staticmethod
    def _normalize_section(section: str) -> str:
        if not section:
            return "unknown"
        s = str(section).strip().lower()
        for canonical, aliases in AnswerGenerator.SECTION_MAP.items():
            if any(alias in s for alias in aliases):
                return canonical.title()
        return "unknown"

    @staticmethod
    def _lexical_similarity(a: str, b: str) -> float:
        ta = {
            t.strip(".,;:()[]{}\"'`").lower()
            for t in (a or "").split()
            if len(t.strip(".,;:()[]{}\"'`")) > 2
        }
        tb = {
            t.strip(".,;:()[]{}\"'`").lower()
            for t in (b or "").split()
            if len(t.strip(".,;:()[]{}\"'`")) > 2
        }
        if not ta or not tb:
            return 0.0
        inter = len(ta.intersection(tb))
        union = len(ta.union(tb))
        return inter / union if union else 0.0

    def _section_weight(self, sub_question: str, section: str) -> float:
        sq = (sub_question or "").lower()
        sec = (section or "unknown").lower()
        if any(k in sq for k in ["method", "approach", "how"]):
            return 1.20 if "method" in sec else 1.0
        if any(k in sq for k in ["result", "performance", "accuracy", "effective"]):
            return 1.20 if "result" in sec else 1.0
        if any(k in sq for k in ["challenge", "limitation", "issue", "risk"]):
            return 1.20 if ("discussion" in sec or "conclusion" in sec) else 1.0
        return 1.0

    def _best_scored_contiguous_window(
        self,
        sentences: List[str],
        scores: List[float],
        min_s: int,
        max_s: int,
    ) -> Dict[str, Any]:
        if not sentences:
            return {"sentences": [], "start": 0, "end": 0, "score": 0.0}

        best = {
            "sentences": sentences[:min_s],
            "start": 0,
            "end": min(len(sentences), min_s),
            "score": -1.0,
        }
        max_len = min(max_s, len(sentences))
        for win_len in range(min_s, max_len + 1):
            for start in range(0, len(sentences) - win_len + 1):
                end = start + win_len
                window = sentences[start:end]
                window_scores = scores[start:end]
                coherence_bonus = 0.1 if self._is_coherent_window(window) else 0.0
                avg_score = (sum(window_scores) / max(1, len(window_scores))) + coherence_bonus
                if avg_score > best["score"]:
                    best = {
                        "sentences": window,
                        "start": start,
                        "end": end,
                        "score": avg_score,
                    }
        return best

    def _build_evidence_paragraph(
        self,
        sub_question: str,
        text: str,
        evidence_extractor,
    ) -> Dict[str, Any]:
        sentences = [self._clean_sentence(s) for s in self._split_sentences(text)]
        sentences = [s for s in sentences if s and not self._is_noise_sentence(s)]
        if not sentences:
            return {
                "paragraph": "",
                "start": 1,
                "end": 1,
                "best_sentence": "",
                "best_score": 0.0,
            }

        scores: List[float] = []
        for s in sentences:
            scores.append(self._lexical_similarity(sub_question, s))

        ranked_ids = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
        top_ids = ranked_ids[: min(len(ranked_ids), self.PARAGRAPH_MAX_SENTENCES)]
        coherent_ids: List[int] = []
        for idx in top_ids:
            if len(coherent_ids) >= self.PARAGRAPH_MAX_SENTENCES:
                break
            candidate = coherent_ids + [idx]
            candidate_sents = [sentences[i] for i in sorted(candidate)]
            if len(candidate_sents) <= 1 or self._is_coherent_window(candidate_sents):
                coherent_ids.append(idx)

        coherent_ids = sorted(coherent_ids)
        contiguous = bool(coherent_ids) and (coherent_ids[-1] - coherent_ids[0] + 1 == len(coherent_ids))
        coherent_ok = len(coherent_ids) >= self.PARAGRAPH_MIN_SENTENCES and self._is_coherent_window([sentences[i] for i in coherent_ids])

        if contiguous or coherent_ok:
            selected = coherent_ids
            if len(selected) < self.PARAGRAPH_MIN_SENTENCES:
                window = self._best_scored_contiguous_window(
                    sentences,
                    scores,
                    self.PARAGRAPH_MIN_SENTENCES,
                    self.PARAGRAPH_MAX_SENTENCES,
                )
                selected = list(range(window["start"], window["end"]))
        else:
            window = self._best_scored_contiguous_window(
                sentences,
                scores,
                self.PARAGRAPH_MIN_SENTENCES,
                self.PARAGRAPH_MAX_SENTENCES,
            )
            selected = list(range(window["start"], window["end"]))

        if not selected:
            return {
                "paragraph": "",
                "start": 1,
                "end": 1,
                "best_sentence": "",
                "best_score": 0.0,
            }

        paragraph = " ".join(sentences[i] for i in selected).strip()
        best_idx = max(selected, key=lambda i: scores[i])
        return {
            "paragraph": paragraph,
            "start": selected[0] + 1,
            "end": selected[-1] + 1,
            "best_sentence": sentences[best_idx],
            "best_score": scores[best_idx],
        }

    def _build_subquestion_conclusion(self, sub_question: str, units: List[Dict[str, Any]]) -> str:
        if not units:
            return "The available evidence is insufficient to draw a reliable conclusion for this sub-question."

        ranked = sorted(
            units,
            key=lambda u: (u.get("final_score", 0.0), u.get("confidence", 0.0)),
            reverse=True,
        )
        top = ranked[:2]
        claim_fragments = []
        for u in top:
            claim = (u.get("claim") or u.get("text") or "").strip()
            if claim:
                claim_fragments.append(claim.rstrip(".") + ".")

        base = " ".join(claim_fragments)
        if not base:
            base = "The evidence points to a consistent pattern across the selected papers."

        confidence_label = self._confidence_band(sum(u.get("confidence", 0.0) for u in top) / max(1, len(top)))
        return (
            f"Based on the selected evidence, {base} "
            f"Overall support for this sub-question is {confidence_label.lower()} confidence."
        )

    def _build_evidence_unit(
        self,
        sub_question: str,
        chunk: Dict[str, Any],
        evidence_extractor,
        subquery_similarity: float,
    ) -> Dict[str, Any] | None:
        text = chunk.get("text", "")
        if not text:
            return None

        if subquery_similarity < self.SUBQUERY_HARD_GATE_THRESHOLD:
            return None

        evidence_sentence = chunk.get("evidence_sentence", "")
        evidence_score = float(chunk.get("evidence_score", 0.0) or 0.0)
        similarity_score = float(chunk.get("similarity_score", 0.0) or 0.0)
        paragraph_info = self._build_evidence_paragraph(sub_question, text, evidence_extractor)
        snippet = paragraph_info.get("paragraph", "")
        sentence_start = int(paragraph_info.get("start", 1))
        sentence_end = int(paragraph_info.get("end", 1))
        if not snippet:
            return None

        evidence_sentence = paragraph_info.get("best_sentence", evidence_sentence)
        evidence_score = max(evidence_score, float(paragraph_info.get("best_score", 0.0) or 0.0))

        verification_score = float(
            chunk.get("verification_score", chunk.get("confidence_score", similarity_score)) or similarity_score
        )

        metadata = chunk.get("metadata") or {}
        section = self._normalize_section(metadata.get("section") or chunk.get("section", "unknown"))
        section_weight = self._section_weight(sub_question, section)

        confidence = max(
            0.0,
            min(
                1.0,
                (self.CONFIDENCE_W1 * subquery_similarity)
                + (self.CONFIDENCE_W2 * evidence_score)
                + (self.CONFIDENCE_W3 * verification_score),
            ),
        )
        final_score = max(
            0.0,
            min(
                1.0,
                ((0.5 * similarity_score) + (0.3 * evidence_score) + (0.2 * subquery_similarity)) * section_weight,
            ),
        )

        return {
            "paper_id": chunk.get("paper_id", ""),
            "paper_title": chunk.get("paper_title", "Unknown"),
            "paper_year": chunk.get("paper_year", "N/A"),
            "section": section,
            "location_start": sentence_start,
            "location_end": sentence_end,
            "relevance": similarity_score,
            "evidence_score": evidence_score,
            "verification_score": verification_score,
            "final_score": final_score,
            "subquery_similarity": subquery_similarity,
            "confidence": confidence,
            "confidence_band": self._confidence_band(confidence),
            "text": snippet,
            "claim": evidence_sentence or snippet,
        }
    
    def generate_answer(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Generate an answer from retrieved chunks.
        
        For MVP: concatenate chunks into structured answer with citations.
        
        Args:
            query: Original user query
            retrieved_chunks: List of retrieved chunk objects
            
        Returns:
            Formatted answer with citations
        """
        if not retrieved_chunks:
            return "I could not find relevant information to answer your question."
        
        try:
            answer = self._build_structured_answer(query, retrieved_chunks)
            return answer
        except Exception as e:
            print(f"✗ Error generating answer: {e}")
            return "Error generating answer from retrieved chunks."
    
    def _build_structured_answer(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Build structured answer from chunks with citations.
        
        Args:
            query: User query
            chunks: Retrieved chunks
            
        Returns:
            Formatted answer
        """
        answer = f"\nQuestion: {query}\n\n"
        answer += "="*80 + "\n"
        answer += "ANSWER\n"
        answer += "="*80 + "\n\n"
        
        # Collect evidence by paper
        evidence_by_paper = {}
        for chunk in chunks:
            paper_key = f"{chunk['paper_title']} ({chunk['paper_year']})"
            if paper_key not in evidence_by_paper:
                evidence_by_paper[paper_key] = []
            evidence_by_paper[paper_key].append(chunk)
        
        # Build answer with citations
        answer_text = "Based on the retrieved research, "
        
        # Add first chunk as main evidence
        if chunks:
            first_chunk = chunks[0]
            answer_text += f"{first_chunk['text']} "
            answer_text += f"[{first_chunk['paper_title']}, {first_chunk['paper_year']}]\n\n"
        
        answer += answer_text
        answer += self._format_citations(evidence_by_paper)
        
        return answer
    
    def _format_citations(self, evidence_by_paper: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format citations section.
        
        Args:
            evidence_by_paper: Dictionary of evidence grouped by paper
            
        Returns:
            Formatted citations
        """
        citations = "="*80 + "\n"
        citations += "EVIDENCE CITATIONS\n"
        citations += "="*80 + "\n\n"
        
        for paper_key, chunks in evidence_by_paper.items():
            citations += f"📄 {paper_key}\n"
            scores = ", ".join([f"{c.get('similarity_score', 0):.4f}" for c in chunks])
            citations += f"   Relevance Scores: {scores}\n"
            citations += f"   Evidence:\n"
            for i, chunk in enumerate(chunks, 1):
                chunk_text = chunk.get('text', '')[:80]
                citations += f"     {i}. {chunk_text}...\n"
            citations += "\n"
        
        return citations
    
    def format_final_output(self, answer: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Format final output with answer and evidence.
        
        Args:
            answer: Generated answer
            retrieved_chunks: Retrieved chunks
            
        Returns:
            Formatted final output
        """
        output = answer
        output += "\n" + "="*80 + "\n"
        output += "RETRIEVED CHUNKS (FOR DEBUGGING)\n"
        output += "="*80 + "\n\n"
        
        for i, chunk in enumerate(retrieved_chunks, 1):
            output += f"Chunk {i}:\n"
            output += f"  Paper: {chunk['paper_title']} ({chunk['paper_year']})\n"
            output += f"  Similarity: {chunk['similarity_score']:.4f}\n"
            output += f"  Text: {chunk['text']}\n\n"
        
        return output
    
    def generate_grouped_answer(
        self, 
        plan: Dict[str, Any], 
        chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Generate grouped answer organized by sub-questions (Stage 3).
        
        Takes the decomposed plan from PlannerAgent and retrieved chunks,
        then organizes the output by sub-question with claims and evidence.
        
        Args:
            plan: Dictionary with main_question, sub_questions, search_queries
            chunks: Retrieved chunks from multi_retrieve
            
        Returns:
            Formatted answer grouped by sub-question
        """
        main_question = plan.get("main_question", "")
        sub_questions = plan.get("sub_questions", [])
        
        if not chunks:
            return "I could not find relevant information to answer your question."
        
        output = f"\n{'='*80}\n"
        output += f"AGENTIC RAG RESPONSE\n"
        output += f"{'='*80}\n\n"
        output += f"📝 Main Question: {main_question}\n\n"
        
        # Match chunks to sub-questions based on similarity
        chunk_assignments = self._assign_chunks_to_subquestions(sub_questions, chunks)

        evidence_extractor = None
        try:
            from src.evidence.extractor import EvidenceExtractor
            evidence_extractor = EvidenceExtractor()
        except Exception:
            evidence_extractor = None
        
        # Generate answer for each sub-question
        globally_used_chunk_ids: set[str] = set()
        for i, sub_q in enumerate(sub_questions, 1):
            output += f"🔹 Sub-question: {sub_q}\n\n"
            
            assigned_chunks = chunk_assignments.get(sub_q, [])

            # Enforce non-repetition across sub-questions.
            unique_for_subq: List[Dict[str, Any]] = []
            for chunk in assigned_chunks:
                cid = str(chunk.get("chunk_id", ""))
                if not cid or cid in globally_used_chunk_ids:
                    continue
                unique_for_subq.append(chunk)
            assigned_chunks = unique_for_subq
            
            if not assigned_chunks:
                output += "  ⚠ No specific evidence found for this sub-question.\n\n"
                continue

            output += "📌 Evidence Units (Grouped by Paper)\n\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            units: List[Dict[str, Any]] = []
            for chunk in assigned_chunks[:8]:
                subquery_similarity = float(
                    chunk.get(
                        "subquery_similarity",
                        chunk.get("query_similarity", chunk.get("similarity_score", 0.0)),
                    )
                    or 0.0
                )
                unit = self._build_evidence_unit(
                    sub_q,
                    chunk,
                    evidence_extractor,
                    subquery_similarity,
                )
                if unit:
                    units.append(unit)
                    cid = str(chunk.get("chunk_id", ""))
                    if cid:
                        globally_used_chunk_ids.add(cid)

            if not units:
                output += "⚠ No sufficiently relevant evidence found for this sub-question.\n\n"
                output += "⚠️ Cross-Paper Conflict Analysis\n"
                output += "No conflict analysis available due to missing evidence.\n\n"
                output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                output += "📊 Comparison Summary\n"
                output += "- Supporting evidence clusters: 0\n"
                output += "- Conflicting clusters: 0\n"
                output += "- Consensus level: Low\n\n"
                continue

            # Deduplicate units by chunk-level claim signature
            dedup_map: Dict[str, Dict[str, Any]] = {}
            for u in units:
                key = f"{u.get('paper_id','')}::{u.get('section','')}::{u.get('claim','')[:100]}"
                if key not in dedup_map or u.get("relevance", 0) > dedup_map[key].get("relevance", 0):
                    dedup_map[key] = u
            units = list(dedup_map.values())

            grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
            for unit in units:
                key = f"{unit['paper_title']} ({unit['paper_year']})"
                section_key = unit.get("section", "unknown")
                grouped.setdefault(key, {})
                grouped[key].setdefault(section_key, []).append(unit)

            for paper_key, section_groups in grouped.items():
                output += f"📄 Paper: {paper_key}\n\n"
                idx = 1
                preferred_sections = self._section_preferences(sub_q)
                ordered_sections = sorted(
                    section_groups.items(),
                    key=lambda kv: (
                        1 if kv[0] in preferred_sections else 0,
                        max(
                            (
                                ((u.get("confidence", 0) * 0.6) + (u.get("relevance", 0) * 0.4))
                                * (self.SECTION_PREFERRED_BOOST if kv[0] in preferred_sections else 1.0)
                            )
                            for u in kv[1]
                        ) if kv[1] else 0,
                    ),
                    reverse=True,
                )[: self.MAX_SECTIONS_PER_PAPER]

                for section_name, section_units in ordered_sections:
                    sorted_units = sorted(
                        section_units,
                        key=lambda u: (u.get("final_score", 0), u.get("confidence", 0), u.get("relevance", 0)),
                        reverse=True,
                    )[: self.TOP_CHUNKS_PER_SECTION]

                    for unit in sorted_units:
                        output += f"[{idx}] Section: {section_name}\n"
                        output += f"Location: sentences {unit['location_start']}–{unit['location_end']}\n"
                        output += (
                            f"Relevance: {unit['relevance']:.2f} | "
                            f"SubQ Similarity: {unit['subquery_similarity']:.2f} | "
                            f"Confidence: {unit['confidence']:.2f} ({unit['confidence_band']})\n\n"
                        )
                        output += "Text:\n"
                        output += f"\"{unit['text']}\"\n\n"
                        output += "---\n\n"
                        idx += 1
                output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            conflicts = ConflictDetector.detect_conflicts(units)
            output += "⚠️ Cross-Paper Conflict Analysis\n\n"
            unique_papers = {u.get("paper_id") for u in units if u.get("paper_id")}
            if len(unique_papers) < 2:
                output += "Only one paper available; cross-paper conflict analysis is not applicable.\n\n"
            elif conflicts:
                first = conflicts[0]
                a = first["a"]
                b = first["b"]
                output += (
                    f"* Claim A ({a['paper_title']} - {a['section']}): \"{(a.get('claim') or '')[:180]}\"\n"
                )
                output += (
                    f"* Claim B ({b['paper_title']} - {b['section']}): \"{(b.get('claim') or '')[:180]}\"\n\n"
                )
                output += f"Conflict Type: {first['type']}\n"
                output += f"Strength: {first['strength']:.2f}\n\n"
                output += f"Explanation: {first.get('explanation','')[:320]}\n\n"
            else:
                output += "No significant conflicts detected because cross-paper claims are either aligned in direction or not sufficiently contradictory within shared topics.\n\n"

            summary = ConflictDetector.comparison_summary(units, conflicts)
            grounded = ConflictDetector.grounded_comparison_statements(units)
            comparison = ConflictDetector.generate_literature_comparison(units)

            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += "📊 Comparison Summary\n"
            output += f"- Supporting evidence clusters: {summary['supporting_clusters']}\n"
            output += f"- Conflicting clusters: {summary['conflicting_clusters']}\n"
            output += f"- Consensus level: {summary['consensus_level']}\n"
            output += "\nCross-paper synthesis:\n"
            output += f"{comparison['paragraph']}\n"
            if comparison.get("support_indices"):
                refs = ", ".join([f"u{idx+1}" for idx in comparison["support_indices"]])
                output += f"Supports: {refs}\n"
            if grounded:
                output += "- Grounded synthesis statements:\n"
                for st in grounded[:3]:
                    refs = [f"u{idx+1}" for idx in st.get("support_indices", [])[:5]]
                    ref_text = ", ".join(refs) if refs else "none"
                    output += f"  • {st.get('text', '').strip()} (supports: {ref_text})\n"

            output += "\n🧩 Final Synthesis\n"
            output += f"{self._build_subquestion_conclusion(sub_q, units)}\n"
            
            output += "\n"
        
        # Summary section
        output += f"{'='*80}\n"
        output += f"SUMMARY\n"
        output += f"{'='*80}\n\n"
        output += f"Total Evidence Sources: {len(chunks)} chunks from {len(set(c.get('paper_id') for c in chunks))} papers\n"
        output += f"Sub-questions Addressed: {len(sub_questions)}\n"
        
        # List all unique papers
        unique_papers = {}
        for chunk in chunks:
            paper_id = chunk.get("paper_id")
            if paper_id not in unique_papers:
                unique_papers[paper_id] = {
                    "title": chunk.get("paper_title"),
                    "year": chunk.get("paper_year")
                }
        
        output += f"\n📚 Papers Referenced:\n"
        for pid, paper in unique_papers.items():
            output += f"   • {paper['title']} ({paper['year']})\n"
        
        return output
    
    # Minimum chunks each sub-question should receive
    MIN_CHUNKS_PER_SUBQ = 0
    # A chunk is multi-assigned to another sub-question only if its score
    # is within this fraction of the best score.  0.80 = must be within 20 %.
    MULTI_ASSIGN_RATIO = 0.80
    # Enable multi-assignment only when we have enough unique chunks
    # to avoid repeating the same single chunk under every sub-question.
    MIN_CHUNKS_FOR_MULTI_ASSIGN_FACTOR = 2
    # Max chunks per sub-question to prevent one sub-q from hoarding everything
    MAX_CHUNKS_PER_SUBQ = 5

    def _assign_chunks_to_subquestions(
        self, 
        sub_questions: List[str], 
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Assign chunks to sub-questions using embedding similarity.

        Strategy
        --------
        1.  Compute cosine similarity of every chunk against every sub-question.
        2.  Primary assignment: each chunk goes to its SINGLE best sub-question
            (exclusive — promotes diversity across sub-questions).
        3.  Multi-assignment: a chunk is also assigned to another sub-question
            only if its score is within MULTI_ASSIGN_RATIO of the best AND the
            target sub-question has fewer than MAX_CHUNKS_PER_SUBQ chunks.
        4.  Guarantee: if any sub-question has < MIN_CHUNKS_PER_SUBQ, backfill
            with unassigned or least-used chunks.

        Args:
            sub_questions: List of sub-questions
            chunks: Retrieved chunks

        Returns:
            Dictionary mapping sub-questions to their assigned chunks
        """
        from src.embeddings.embedder import get_shared_embedder

        assignments: Dict[str, List[Dict[str, Any]]] = {sq: [] for sq in sub_questions}
        # Track chunk_ids per sub-question to prevent duplicates
        assigned_ids: Dict[str, set] = {sq: set() for sq in sub_questions}

        if not sub_questions or not chunks:
            return assignments

        # Deduplicate input chunks by chunk_id first
        seen_chunk_ids: set = set()
        unique_chunks: List[Dict[str, Any]] = []
        for c in chunks:
            cid = c.get("chunk_id", id(c))
            if cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                unique_chunks.append(c)
        chunks = unique_chunks

        embedder = get_shared_embedder()

        # ── 1. Embed everything ──────────────────────────────────
        sq_embeddings = [embedder.embed_text(sq) for sq in sub_questions]
        chunk_embeddings = [embedder.embed_text(c.get("text", "")) for c in chunks]

        # score_matrix[i][j] = similarity(chunk_i, sub_question_j)
        score_matrix: List[List[float]] = []
        for c_emb in chunk_embeddings:
            row = [float(np.dot(c_emb, sq_emb)) for sq_emb in sq_embeddings]
            score_matrix.append(row)

        # ── 2. Primary assignment (exclusive) ────────────────────
        min_threshold = Config.SUBQUESTION_ASSIGN_THRESHOLD
        chunk_assigned_to: Dict[int, int] = {}  # chunk_index -> primary sub_q index

        for i, chunk in enumerate(chunks):
            if not chunk.get("text"):
                continue
            cid = chunk.get("chunk_id", id(chunk))

            scores = score_matrix[i]
            best_j = int(np.argmax(scores))
            best_score = scores[best_j]

            if best_score >= min_threshold:
                sq = sub_questions[best_j]
                if len(assignments[sq]) < self.MAX_CHUNKS_PER_SUBQ and cid not in assigned_ids[sq]:
                    assignments[sq].append({**chunk, "subquery_similarity": best_score})
                    assigned_ids[sq].add(cid)
                    chunk_assigned_to[i] = best_j

        # ── 3. Selective multi-assignment ─────────────────────────
        # Only allow multi-assignment when there is sufficient evidence.
        min_chunks_for_multi_assign = max(
            1,
            len(sub_questions) * self.MIN_CHUNKS_FOR_MULTI_ASSIGN_FACTOR,
        )
        allow_multi_assign = len(chunks) >= min_chunks_for_multi_assign

        if allow_multi_assign:
            for i, chunk in enumerate(chunks):
                if not chunk.get("text"):
                    continue
                cid = chunk.get("chunk_id", id(chunk))

                scores = score_matrix[i]
                best_score = max(scores)
                threshold = best_score * self.MULTI_ASSIGN_RATIO

                for j, sc in enumerate(scores):
                    if j == chunk_assigned_to.get(i):
                        continue  # already primary-assigned here
                    if sc >= threshold and sc >= min_threshold:
                        sq = sub_questions[j]
                        if len(assignments[sq]) < self.MAX_CHUNKS_PER_SUBQ and cid not in assigned_ids[sq]:
                            assignments[sq].append({**chunk, "subquery_similarity": sc})
                            assigned_ids[sq].add(cid)

        # ── 4. Optional back-fill guarantee ──────────────────────
        if self.MIN_CHUNKS_PER_SUBQ <= 0:
            return assignments

        for j, sq in enumerate(sub_questions):
            if len(assignments[sq]) >= self.MIN_CHUNKS_PER_SUBQ:
                continue

            ranked = sorted(
                range(len(chunks)),
                key=lambda idx: score_matrix[idx][j],
                reverse=True,
            )
            for idx in ranked:
                if len(assignments[sq]) >= self.MIN_CHUNKS_PER_SUBQ:
                    break
                if score_matrix[idx][j] < min_threshold:
                    continue
                cid = chunks[idx].get("chunk_id", id(chunks[idx]))
                if cid not in assigned_ids[sq]:
                    assignments[sq].append({**chunks[idx], "subquery_similarity": score_matrix[idx][j]})
                    assigned_ids[sq].add(cid)

        return assignments
