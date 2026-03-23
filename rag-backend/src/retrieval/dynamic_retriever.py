"""Dynamic Retriever - Fetches papers on-the-fly with abstract relevance filtering."""

import numpy as np
from typing import List, Dict, Any, Optional
from src.embeddings.embedder import get_embedder
from src.database import get_mongo_client
from src.ingestion.loader import PaperIngestor
from src.ingestion.fulltext import FullTextFetcher
from src.chunking.processor import TextChunker
from src.config import Config


class DynamicRetriever:
    """
    Two-stage Dynamic Retriever for real-time paper fetching and retrieval.
    
    Stage A  – Abstract Relevance Filter:
        1. Fetch papers from APIs (with abstracts)
        2. Embed each abstract & compare to query
        3. Keep only papers whose abstract is relevant (above threshold)
    
    Stage B  – Full-Text Fetch & Chunk:
        4. For relevant papers, try to download full text (PDF/HTML)
        5. Chunk full text (or abstract as fallback)
        6. Embed chunks & similarity search
        7. Return top-k with evidence
    """
    
    # Minimum cosine similarity between abstract embedding and query
    ABSTRACT_RELEVANCE_THRESHOLD = 0.35
    
    def __init__(self, use_evidence: bool = True, papers_per_query: int = 5):
        """
        Initialize DynamicRetriever.
        
        Args:
            use_evidence: Enable sentence-level evidence extraction
            papers_per_query: Number of papers to fetch per search query
        """
        self.embedder = get_embedder()
        self.mongo = get_mongo_client()
        self.ingestor = PaperIngestor(source="openalex")
        self.fulltext_fetcher = FullTextFetcher()
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
        Two-stage dynamic retrieval:
        
        Stage A: Fetch abstracts → score relevance → filter
        Stage B: Fetch full text for relevant papers → chunk → embed → retrieve
        
        Args:
            search_queries: List of search queries from PlannerAgent
            main_query: Original user question
            top_k: Number of top chunks to return
            
        Returns:
            List of relevant chunks with metadata and evidence
        """
        print(f"\n🌐 DYNAMIC RETRIEVAL MODE (two-stage)")
        print(f"   Fetching papers for {len(search_queries)} search queries...")
        
        # Connect to MongoDB
        self.mongo.connect()
        papers_collection = self.mongo.get_papers_collection()
        chunks_collection = self.mongo.get_chunks_collection()
        
        # ──────────────────────────────────────────────────────────
        # STAGE A: Fetch abstracts & filter by relevance
        # ──────────────────────────────────────────────────────────
        print(f"\n📋 STAGE A: Abstract Relevance Filtering")
        
        # Step 1: Fetch papers for each search query
        all_papers = []
        for query in search_queries:
            print(f"   → Fetching papers for: {query[:60]}...")
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
        
        # Step 2: Deduplicate
        unique_papers = {}
        for paper in all_papers:
            pid = paper.get("paper_id")
            if pid and pid not in unique_papers:
                unique_papers[pid] = paper
        
        print(f"   ✓ Total unique papers: {len(unique_papers)}")
        
        # Step 3: Check MongoDB for existing papers (with full text already stored)
        existing_paper_ids = []
        new_paper_ids = []
        
        for pid, paper in unique_papers.items():
            existing = papers_collection.find_one({"paper_id": pid})
            if existing:
                existing_paper_ids.append(pid)
                # If existing record has full_text, update our in-memory copy
                if existing.get("full_text"):
                    unique_papers[pid]["full_text"] = existing["full_text"]
            else:
                new_paper_ids.append(pid)
        
        print(f"     → Already in DB: {len(existing_paper_ids)} (reusing)")
        print(f"     → New papers: {len(new_paper_ids)}")
        
        # Step 4: Score abstract relevance against the query (BATCHED)
        print(f"   🔍 Scoring abstract relevance...")
        all_queries = search_queries + [main_query]
        all_query_embs = self.embedder.embed_batch(all_queries)
        search_embs = all_query_embs[:-1]
        query_emb = all_query_embs[-1]

        # Batch-embed all abstracts at once
        papers_with_abstract = [(pid, paper) for pid, paper in unique_papers.items()
                                if paper.get("abstract")]
        abstract_texts = [p.get("abstract", "") for _, p in papers_with_abstract]
        
        relevant_papers = []
        irrelevant_count = len(unique_papers) - len(papers_with_abstract)  # no-abstract papers

        if abstract_texts:
            abstract_embs = self.embedder.embed_batch(abstract_texts)
            for i, (pid, paper) in enumerate(papers_with_abstract):
                max_score = float(np.max(abstract_embs[i] @ all_query_embs.T))
                paper["_abstract_relevance"] = max_score
                if max_score >= self.ABSTRACT_RELEVANCE_THRESHOLD:
                    relevant_papers.append(paper)
                else:
                    irrelevant_count += 1
        
        relevant_papers.sort(key=lambda p: p.get("_abstract_relevance", 0), reverse=True)
        
        print(f"   ✓ Relevant papers: {len(relevant_papers)} (threshold={self.ABSTRACT_RELEVANCE_THRESHOLD})")
        print(f"   ✗ Filtered out: {irrelevant_count} irrelevant papers")
        
        if not relevant_papers:
            print("   ❌ No papers passed the relevance filter")
            return []
        
        for i, p in enumerate(relevant_papers[:5], 1):
            score = p.get("_abstract_relevance", 0)
            has_url = "📄" if p.get("full_text_url") or p.get("best_oa_pdf_url") else "  "
            print(f"     {i}. [{score:.3f}] {has_url} {p.get('title', 'Unknown')[:70]}")
        
        # ──────────────────────────────────────────────────────────
        # STAGE B: Full-text fetch, chunk, embed, retrieve
        # ──────────────────────────────────────────────────────────
        print(f"\n📖 STAGE B: Full-Text Fetch & Retrieval")
        
        # Step 5: Fetch full text for relevant papers that don't already have it
        fulltext_success = 0
        fulltext_failed = 0
        abstract_only = 0
        
        for paper in relevant_papers:
            # Skip if we already have full text
            if paper.get("full_text"):
                fulltext_success += 1
                continue
            
            has_oa_url = paper.get("full_text_url") or paper.get("best_oa_pdf_url") or paper.get("oa_url")
            if has_oa_url:
                print(f"   📥 Downloading: {paper.get('title', 'Unknown')[:55]}...")
                full_text = self.fulltext_fetcher.fetch_full_text(paper)
                if full_text:
                    paper["full_text"] = full_text
                    fulltext_success += 1
                else:
                    fulltext_failed += 1
                    abstract_only += 1
            else:
                abstract_only += 1
        
        print(f"   ✓ Full text obtained: {fulltext_success} papers")
        if fulltext_failed:
            print(f"   ⚠ Full text failed: {fulltext_failed} papers (using abstract)")
        if abstract_only:
            print(f"   📝 Abstract only: {abstract_only} papers")
        
        # Step 6: Get existing chunks from MongoDB for DB papers WITHOUT new full text
        existing_chunks = []
        relevant_pids = {p["paper_id"] for p in relevant_papers}
        reuse_ids = [pid for pid in existing_paper_ids
                     if pid in relevant_pids
                     and not unique_papers.get(pid, {}).get("full_text")]
        
        if reuse_ids:
            existing_chunks = list(chunks_collection.find({"paper_id": {"$in": reuse_ids}}))
            print(f"   ✓ Retrieved {len(existing_chunks)} existing chunks from DB")
        
        # Step 7: Chunk relevant papers (new or those with fresh full text)
        papers_to_chunk = [p for p in relevant_papers if p.get("paper_id") not in reuse_ids]
        new_chunks = []
        
        if papers_to_chunk:
            print(f"   📝 Chunking {len(papers_to_chunk)} papers...")
            new_chunks = self.chunker.create_chunks(papers_to_chunk)
            print(f"   ✓ Created {len(new_chunks)} new chunks")
            
            # Store in MongoDB
            for paper in papers_to_chunk:
                try:
                    store_paper = {k: v for k, v in paper.items() if not k.startswith("_")}
                    papers_collection.update_one(
                        {"paper_id": store_paper["paper_id"]},
                        {"$set": store_paper},
                        upsert=True
                    )
                except Exception:
                    pass
            
            for chunk in new_chunks:
                try:
                    chunks_collection.insert_one(chunk)
                except Exception:
                    pass
            
            print(f"   💾 Stored papers and chunks in MongoDB")
        
        # Step 8: Combine all chunks
        all_chunks = []
        
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
        
        # Step 9: Embed all chunks (BATCHED)
        print(f"   🧠 Embedding {len(all_chunks)} chunks (batched)...")
        chunk_texts = [c["text"] for c in all_chunks]
        chunk_embeddings = self.embedder.embed_batch(chunk_texts)
        print(f"   ✓ Generated {len(chunk_embeddings)} embeddings")
        
        # Step 10: Similarity search (unified scorer)
        print(f"   🔍 Searching for relevant chunks...")
        from src.retrieval.scorer import SimilarityScorer
        
        top_indices, best_scores = SimilarityScorer.get_top_matches(
            chunk_embeddings=chunk_embeddings,
            query_embeddings=all_query_embs,
            top_k=top_k
        )

        chunk_scores = []
        for idx in top_indices:
            # Get best query index for this chunk
            scores_matrix = chunk_embeddings @ all_query_embs.T
            qi = int(np.argmax(scores_matrix[idx, :]))
            matched = search_queries[qi] if qi < len(search_queries) else main_query
            chunk_scores.append({"index": int(idx), "score": float(best_scores[idx]), "matched_query": matched})

        top_chunks = chunk_scores
        
        # Build results
        results = []
        for item in top_chunks:
            idx = item["index"]
            chunk = all_chunks[idx]
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
                "paper_full_text_url": paper.get("full_text_url", ""),
                "has_full_text": bool(paper.get("full_text")),
                "similarity_score": item["score"],
                "section": chunk.get("section", "abstract"),
                "matched_query": item["matched_query"],
                "source": chunk.get("source", "unknown"),
            }
            results.append(result)
        
        body_chunks = sum(1 for r in results if r.get("section") == "body")
        abstract_chunks = sum(1 for r in results if r.get("section") == "abstract")
        print(f"   ✓ Found {len(results)} relevant chunks ({body_chunks} from full text, {abstract_chunks} from abstracts)")
        
        # Step 11: Extract sentence-level evidence
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
