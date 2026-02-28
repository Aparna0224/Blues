"""Answer generation with citations."""

from typing import List, Dict, Any


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
            
            for j, chunk in enumerate(assigned_chunks[:3], 1):  # Max 3 per sub-question
                text = chunk.get("text", "")
                paper_title = chunk.get("paper_title", "Unknown")
                paper_year = chunk.get("paper_year", "N/A")
                score = chunk.get("similarity_score", 0)
                evidence_sentence = chunk.get("evidence_sentence", "")
                evidence_score = chunk.get("evidence_score", 0)
                
                output += f"    [{j}] Claim:\n"
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
    
    def _assign_chunks_to_subquestions(
        self, 
        sub_questions: List[str], 
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Assign chunks to the most relevant sub-question.
        
        Uses simple keyword matching for MVP. Could be enhanced with
        embedding similarity in future versions.
        
        Args:
            sub_questions: List of sub-questions
            chunks: Retrieved chunks
            
        Returns:
            Dictionary mapping sub-questions to their assigned chunks
        """
        assignments: Dict[str, List[Dict[str, Any]]] = {sq: [] for sq in sub_questions}
        
        # If chunk has matched_query, use that for assignment
        query_to_subq = {}
        for sq in sub_questions:
            # Normalize for matching
            sq_words = set(sq.lower().split())
            query_to_subq[sq] = sq_words
        
        for chunk in chunks:
            matched_query = chunk.get("matched_query", "")
            chunk_text = chunk.get("text", "").lower()
            
            best_match = None
            best_score = 0
            
            for sq, sq_words in query_to_subq.items():
                # Score based on word overlap between sub-question and chunk text
                score = len(sq_words.intersection(set(chunk_text.split())))
                
                # Bonus if matched_query contains sub-question keywords
                if matched_query:
                    matched_words = set(matched_query.lower().split())
                    score += len(sq_words.intersection(matched_words)) * 2
                
                if score > best_score:
                    best_score = score
                    best_match = sq
            
            if best_match:
                assignments[best_match].append(chunk)
            elif sub_questions:
                # Assign to first sub-question as fallback
                assignments[sub_questions[0]].append(chunk)
        
        return assignments
