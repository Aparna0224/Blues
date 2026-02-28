"""Answer generation with citations."""

from typing import List, Dict, Any
import numpy as np


class AnswerGenerator:
    """Generate answers from retrieved chunks with proper citations."""
    
    def __init__(self):
        pass
    
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
        
        # Generate answer for each sub-question
        for i, sub_q in enumerate(sub_questions, 1):
            output += f"{'─'*60}\n"
            output += f"🔹 Sub-Question {i}: {sub_q}\n"
            output += f"{'─'*60}\n\n"
            
            assigned_chunks = chunk_assignments.get(sub_q, [])
            
            if not assigned_chunks:
                output += "  ⚠ No specific evidence found for this sub-question.\n\n"
                continue
            
            # Generate claims with evidence
            output += "  📌 Claims & Evidence:\n\n"
            
            for j, chunk in enumerate(assigned_chunks[:5], 1):  # Max 5 per sub-question
                text = chunk.get("text", "")
                paper_title = chunk.get("paper_title", "Unknown")
                paper_year = chunk.get("paper_year", "N/A")
                score = chunk.get("similarity_score", 0)
                evidence_sentence = chunk.get("evidence_sentence", "")
                evidence_score = chunk.get("evidence_score", 0)
                section = chunk.get("section", "body")

                # Human-readable section label
                section_label = self._format_section_label(section)

                output += f"    [{j}] Claim ({section_label}):\n"
                if evidence_sentence:
                    output += f"        \"{evidence_sentence}\"\n"
                    output += f"        Evidence Score: {evidence_score:.4f}\n"
                else:
                    # Truncate text for display
                    display_text = text[:200] + "..." if len(text) > 200 else text
                    output += f"        \"{display_text}\"\n"
                
                output += f"        📄 Source: {paper_title} ({paper_year})\n"
                output += f"        Similarity: {score:.4f}\n\n"
            
            output += "\n"
        
        # Summary section
        output += f"{'='*80}\n"
        output += f"SUMMARY\n"
        output += f"{'='*80}\n\n"
        output += f"Total Evidence Sources: {len(chunks)} chunks from {len(set(c.get('paper_id') for c in chunks))} papers\n"
        output += f"Sub-questions Addressed: {len(sub_questions)}\n"

        # Section breakdown
        from collections import Counter
        section_counts = Counter(c.get("section", "body") for c in chunks)
        if section_counts:
            output += f"\n📊 Evidence by Section:\n"
            for sec, cnt in section_counts.most_common():
                label = self._format_section_label(sec)
                output += f"   • {label}: {cnt} chunk{'s' if cnt != 1 else ''}\n"
        
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
    MIN_CHUNKS_PER_SUBQ = 2
    # A chunk is assigned to a sub-question if its score is within this
    # fraction of the best score  (e.g. 0.95 → within 5 %)
    MULTI_ASSIGN_RATIO = 0.95

    # ── Section label formatting ─────────────────────────────────

    _SECTION_LABELS = {
        "abstract": "Abstract",
        "introduction": "Introduction",
        "background": "Background",
        "literature_review": "Literature Review",
        "methodology": "Methodology",
        "results": "Results",
        "discussion": "Discussion",
        "conclusion": "Conclusion",
        "body": "Full Text",
    }

    @classmethod
    def _format_section_label(cls, section: str) -> str:
        """Return a human-readable label for a section key."""
        return cls._SECTION_LABELS.get(section, section.replace("_", " ").title())

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
        2.  Primary assignment: each chunk goes to its best-matching sub-question.
        3.  Multi-assignment: if a chunk's score for another sub-question is
            within MULTI_ASSIGN_RATIO of the best score, assign it there too.
        4.  Guarantee: if any sub-question still has < MIN_CHUNKS_PER_SUBQ,
            fill it with the globally highest-scoring unassigned chunks for
            that sub-question (round-robin backfill).

        Args:
            sub_questions: List of sub-questions
            chunks: Retrieved chunks

        Returns:
            Dictionary mapping sub-questions to their assigned chunks
        """
        from src.embeddings.embedder import get_embedder

        assignments: Dict[str, List[Dict[str, Any]]] = {sq: [] for sq in sub_questions}

        if not sub_questions or not chunks:
            return assignments

        embedder = get_embedder()

        # ── 1. Embed everything (batched) ────────────────────────
        sq_embeddings = embedder.embed_batch(sub_questions)
        chunk_texts = [c.get("text", "") for c in chunks]
        chunk_embeddings = embedder.embed_batch(chunk_texts)

        # score_matrix: (num_chunks, num_sub_questions) via matrix multiply
        score_matrix = chunk_embeddings @ sq_embeddings.T

        # ── 2. Primary + multi assignment ────────────────────────
        for i, chunk in enumerate(chunks):
            if not chunk.get("text"):
                continue

            scores = score_matrix[i]
            best_score = max(scores)
            threshold = best_score * self.MULTI_ASSIGN_RATIO

            for j, sc in enumerate(scores):
                if sc >= threshold:
                    assignments[sub_questions[j]].append(chunk)

        # ── 3. Back-fill guarantee ───────────────────────────────
        for j, sq in enumerate(sub_questions):
            if len(assignments[sq]) >= self.MIN_CHUNKS_PER_SUBQ:
                continue

            # Rank all chunks by their score for this sub-question (desc)
            ranked = sorted(
                range(len(chunks)),
                key=lambda idx: score_matrix[idx][j],
                reverse=True,
            )
            existing_texts = {id(c) for c in assignments[sq]}
            for idx in ranked:
                if len(assignments[sq]) >= self.MIN_CHUNKS_PER_SUBQ:
                    break
                if id(chunks[idx]) not in existing_texts:
                    assignments[sq].append(chunks[idx])
                    existing_texts.add(id(chunks[idx]))

        return assignments
