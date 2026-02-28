"""Dynamic Retriever - Fetches papers on-the-fly during query time."""

import numpy as np
from typing import List, Dict, Any, Optional
from src.embeddings.embedder import EmbeddingGenerator
from src.database import get_mongo_client
from src.ingestion.loader import PaperIngestor
from src.chunking.processor import TextChunker
from src.config import Config


class DynamicRetriever:
    """
    Dynamic Retriever for real-time paper fetching and retrieval.
    
    Unlike the standard Retriever which searches pre-indexed papers,
    this retriever:
    1. Fetches new papers from APIs based on search queries
    2. Chunks and embeds them on-the-fly
    3. Performs similarity search on fresh data
    4. Returns relevant evidence
    
    This is slower but ensures the most relevant papers are retrieved
    for each specific query.
    """
    
    def __init__(self, use_evidence: bool = True, papers_per_query: int = 5):
        """
        Initialize DynamicRetriever.
        
        Args:
            use_evidence: Enable sentence-level evidence extraction
            papers_per_query: Number of papers to fetch per search query
        """
        self.embedder = EmbeddingGenerator()
        self.mongo = get_mongo_client()
        self.ingestor = PaperIngestor(source="openalex")
        self.chunker = TextChunker()
        self.use_evidence = use_evidence
        self.papers_per_query = papers_per_query
        self._evidence_extractor = None
    
    @property
    def evidence_extractor(self):
        """Lazy load evidence extractor only when needed."""
        if self._evidence_extractor is None and self.use_evidence:
            from src.evidence.extractor import EvidenceExtractor
            self._evidence_extractor = EvidenceExtractor()
        return self._evidence_extractor
    
    def dynamic_retrieve(
        self,
        search_queries: List[str],
        main_query: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Dynamically fetch papers, embed, and retrieve relevant chunks.
        
        Checks MongoDB for existing papers to avoid duplication:
        - Papers already in DB: reuse existing chunks
        - New papers: fetch, chunk, embed, and optionally store
        
        Args:
            search_queries: List of search queries from PlannerAgent
            main_query: Original user question (for evidence extraction)
            top_k: Number of top chunks to return
            
        Returns:
            List of relevant chunks with metadata and evidence
        """
        print(f"\n🌐 DYNAMIC RETRIEVAL MODE")
        print(f"   Fetching papers for {len(search_queries)} search queries...")
        
        # Connect to MongoDB
        self.mongo.connect()
        papers_collection = self.mongo.get_papers_collection()
        chunks_collection = self.mongo.get_chunks_collection()
        
        # Step 1: Fetch papers for each search query
        all_papers = []
        for query in search_queries:
            print(f"   → Fetching papers for: {query[:50]}...")
            try:
                papers = self.ingestor.fetch_papers(query, max_results=self.papers_per_query)
                if papers:
                    all_papers.extend(papers)
                    print(f"     ✓ Found {len(papers)} papers")
            except Exception as e:
                print(f"     ⚠ Error fetching: {e}")
                continue
        
        if not all_papers:
            print("   ❌ No papers found from APIs")
            return []
        
        # Step 2: Deduplicate and check MongoDB for existing papers
        unique_papers = {}
        existing_paper_ids = []
        new_papers = []
        
        for paper in all_papers:
            pid = paper.get("paper_id")
            if not pid or pid in unique_papers:
                continue
            
            unique_papers[pid] = paper
            
            # Check if paper already exists in MongoDB
            existing = papers_collection.find_one({"paper_id": pid})
            if existing:
                existing_paper_ids.append(pid)
            else:
                new_papers.append(paper)
        
        print(f"   ✓ Total unique papers: {len(unique_papers)}")
        print(f"     → Already in DB: {len(existing_paper_ids)} (reusing chunks)")
        print(f"     → New papers: {len(new_papers)} (will chunk & embed)")
        
        # Step 3: Get existing chunks from MongoDB
        existing_chunks = []
        if existing_paper_ids:
            existing_chunks = list(chunks_collection.find({
                "paper_id": {"$in": existing_paper_ids}
            }))
            print(f"   ✓ Retrieved {len(existing_chunks)} existing chunks from DB")
        
        # Step 4: Chunk and store new papers
        new_chunks = []
        if new_papers:
            print(f"   📝 Chunking {len(new_papers)} new papers...")
            new_chunks = self.chunker.create_chunks(new_papers)
            print(f"   ✓ Created {len(new_chunks)} new chunks")
            
            # Store new papers and chunks in MongoDB for future use
            for paper in new_papers:
                try:
                    papers_collection.insert_one(paper)
                except Exception as e:
                    pass  # Ignore duplicate key errors
            
            for chunk in new_chunks:
                try:
                    chunks_collection.insert_one(chunk)
                except Exception as e:
                    pass  # Ignore duplicate key errors
            
            print(f"   💾 Stored {len(new_papers)} papers and {len(new_chunks)} chunks in MongoDB")
        
        # Step 5: Combine all chunks
        all_chunks = []
        
        # Convert MongoDB documents to dicts and add paper metadata
        for chunk in existing_chunks:
            paper = unique_papers.get(chunk.get("paper_id"), {})
            all_chunks.append({
                "chunk_id": chunk.get("chunk_id"),
                "text": chunk.get("text", ""),
                "paper_id": chunk.get("paper_id"),
                "paper_title": paper.get("title", chunk.get("paper_title", "Unknown")),
                "paper_year": paper.get("year", chunk.get("paper_year", "N/A")),
                "section": chunk.get("section", "abstract"),
                "source": "existing"
            })
        
        for chunk in new_chunks:
            paper = unique_papers.get(chunk.get("paper_id"), {})
            all_chunks.append({
                "chunk_id": chunk.get("chunk_id"),
                "text": chunk.get("text", ""),
                "paper_id": chunk.get("paper_id"),
                "paper_title": paper.get("title", "Unknown"),
                "paper_year": paper.get("year", "N/A"),
                "section": chunk.get("section", "abstract"),
                "source": "new"
            })
        
        if not all_chunks:
            print("   ❌ No chunks available")
            return []
        
        print(f"   ✓ Total chunks to search: {len(all_chunks)}")
        
        # Step 6: Embed all chunks
        print(f"   🧠 Embedding chunks...")
        chunk_embeddings = []
        for chunk in all_chunks:
            emb = self.embedder.embed_text(chunk["text"])
            chunk_embeddings.append(emb)
        
        chunk_embeddings = np.array(chunk_embeddings)
        print(f"   ✓ Generated {len(chunk_embeddings)} embeddings")
        
        # Step 7: Embed queries and find similar chunks
        print(f"   🔍 Searching for relevant chunks...")
        
        query_embeddings = []
        for sq in search_queries:
            qe = self.embedder.embed_text(sq)
            query_embeddings.append(qe)
        
        main_emb = self.embedder.embed_text(main_query)
        query_embeddings.append(main_emb)
        
        # Calculate similarity scores for each chunk against all queries
        # Use max similarity across all queries for each chunk
        chunk_scores = []
        for i, chunk_emb in enumerate(chunk_embeddings):
            max_score = 0
            best_query = ""
            for j, q_emb in enumerate(query_embeddings):
                # Cosine similarity (embeddings are already normalized)
                score = float(np.dot(chunk_emb, q_emb))
                if score > max_score:
                    max_score = score
                    if j < len(search_queries):
                        best_query = search_queries[j]
                    else:
                        best_query = main_query
            
            chunk_scores.append({
                "index": i,
                "score": max_score,
                "matched_query": best_query
            })
        
        # Sort by score and take top_k
        chunk_scores.sort(key=lambda x: x["score"], reverse=True)
        top_chunks = chunk_scores[:top_k]
        
        # Build results
        results = []
        for item in top_chunks:
            idx = item["index"]
            chunk = all_chunks[idx]
            
            # Find paper metadata
            paper_id = chunk.get("paper_id")
            paper = unique_papers.get(paper_id, {})
            
            result = {
                "chunk_id": chunk.get("chunk_id", f"dyn_{idx}"),
                "text": chunk.get("text", ""),
                "paper_id": paper_id,
                "paper_title": chunk.get("paper_title") or paper.get("title", "Unknown"),
                "paper_year": chunk.get("paper_year") or paper.get("year", "N/A"),
                "paper_authors": paper.get("authors", []),
                "paper_doi": paper.get("doi", ""),
                "similarity_score": item["score"],
                "section": chunk.get("section", "abstract"),
                "matched_query": item["matched_query"],
                "source": chunk.get("source", "unknown")  # "existing" or "new"
            }
            results.append(result)
        
        print(f"   ✓ Found {len(results)} relevant chunks")
        
        # Step 8: Extract sentence-level evidence
        if self.use_evidence and results:
            print(f"   📌 Extracting sentence-level evidence...")
            results = self._extract_evidence(main_query, results)
        
        return results
    
    def _extract_evidence(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract sentence-level evidence from chunks.
        
        Args:
            query: The user query
            chunks: Retrieved chunks
            
        Returns:
            Chunks enhanced with evidence_sentence and evidence_score
        """
        if not self.evidence_extractor:
            return chunks
        
        enhanced_chunks = self.evidence_extractor.extract_evidence_from_chunks(query, chunks)
        print(f"   ✓ Extracted evidence from {len(enhanced_chunks)} chunks")
        
        return enhanced_chunks
