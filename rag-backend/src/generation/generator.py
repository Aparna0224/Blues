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
            citations += f"   Relevance Scores: {', '.join([f'{c['similarity_score']:.4f}' for c in chunks])}\n"
            citations += f"   Evidence:\n"
            for i, chunk in enumerate(chunks, 1):
                citations += f"     {i}. {chunk['text'][:80]}...\n"
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
