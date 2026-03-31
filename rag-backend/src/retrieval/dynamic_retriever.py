"""Dynamic Retriever - Fetches papers on-the-fly with abstract relevance filtering."""

import numpy as np
from typing import List, Dict, Any, Optional
from src.embeddings.embedder import get_shared_embedder
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
    ABSTRACT_RELEVANCE_THRESHOLD = Config.DYNAMIC_ABSTRACT_MIN_SIMILARITY
    
    def __init__(self, use_evidence: bool = True, papers_per_query: int = 5):
        """
        Initialize DynamicRetriever.
        
        Args:
            use_evidence: Enable sentence-level evidence extraction
            papers_per_query: Number of papers to fetch per search query
        """
        self.embedder = get_shared_embedder()
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
        top_k: int = 10,
        metadata_filters: Dict[str, Any] | None = None,
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
        
        # Step 4: Score abstract relevance against the query
        print(f"   🔍 Scoring abstract relevance...")
        query_emb = self.embedder.embed_text(main_query)
        search_embs = [self.embedder.embed_text(sq) for sq in search_queries]
        all_query_embs = search_embs + [query_emb]
        
        relevant_papers = []
        irrelevant_count = 0
        
        for pid, paper in unique_papers.items():
            abstract = paper.get("abstract", "")
            if not abstract:
                irrelevant_count += 1
                continue
            
            abstract_emb = self.embedder.embed_text(abstract)
            max_score = max(float(np.dot(abstract_emb, qe)) for qe in all_query_embs)
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
        
        # Step 6: Get existing chunks from MongoDB for DB papers that already have chunks
        existing_chunks = []
        relevant_pids = {p["paper_id"] for p in relevant_papers}
        
        # Reuse papers that are already in DB AND have chunks stored
        # Skip reuse only if we just downloaded new full_text for a paper that
        # previously only had abstract chunks
        reuse_ids = []
        for pid in existing_paper_ids:
            if pid not in relevant_pids:
                continue
            # Check if paper has existing chunks in DB
            has_chunks = chunks_collection.count_documents({"paper_id": pid}, limit=1) > 0
            has_new_fulltext = unique_papers.get(pid, {}).get("full_text") and not chunks_collection.find_one({"paper_id": pid, "section": "body"})
            if has_chunks and not has_new_fulltext:
                reuse_ids.append(pid)
        
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
            
            print(f"   💾 Stored papers and chunks in MongoDB")
        
        # Step 8: Combine all chunks and build embeddings
        # For existing chunks, reuse stored embeddings; for new chunks, compute them
        all_chunks = []
        all_embeddings = []
        
        # Process existing chunks — reuse embeddings from MongoDB
        existing_with_emb = 0
        existing_need_emb = []
        for chunk in existing_chunks:
            paper = unique_papers.get(chunk.get("paper_id"), {})
            entry = {
                "chunk_id": chunk.get("chunk_id"),
                "text": chunk.get("text", ""),
                "paper_id": chunk.get("paper_id"),
                "paper_title": paper.get("title", chunk.get("paper_title", "Unknown")),
                "paper_year": paper.get("year", chunk.get("paper_year", "N/A")),
                "section": chunk.get("section", "abstract"),
                "source": "existing",
                "metadata": chunk.get("metadata"),
            }
            all_chunks.append(entry)
            
            # Reuse stored embedding if available
            stored_emb = chunk.get("embedding")
            if stored_emb is not None and len(stored_emb) == Config.EMBEDDING_DIMENSION:
                all_embeddings.append(np.array(stored_emb, dtype=np.float32))
                existing_with_emb += 1
            else:
                existing_need_emb.append(len(all_chunks) - 1)  # index for later
                all_embeddings.append(None)  # placeholder
        
        if existing_with_emb:
            print(f"   ✓ Reused {existing_with_emb} cached embeddings from DB")
        
        # Process new chunks
        for chunk in new_chunks:
            paper = unique_papers.get(chunk.get("paper_id"), {})
            all_chunks.append({
                "chunk_id": chunk.get("chunk_id"),
                "text": chunk.get("text", ""),
                "paper_id": chunk.get("paper_id"),
                "paper_title": paper.get("title", "Unknown"),
                "paper_year": paper.get("year", "N/A"),
                "section": chunk.get("section", "abstract"),
                "source": "new",
                "metadata": chunk.get("metadata"),
            })
            all_embeddings.append(None)  # need to compute
        
        if not all_chunks:
            print("   ❌ No chunks available")
            return []
        
        print(f"   ✓ Total chunks to search: {len(all_chunks)}")
        
        # Step 9: Embed only chunks that don't have cached embeddings
        indices_needing_emb = [i for i, e in enumerate(all_embeddings) if e is None]
        
        if indices_needing_emb:
            texts_to_embed = [all_chunks[i]["text"] for i in indices_needing_emb]
            print(f"   🧠 Embedding {len(texts_to_embed)} new chunks (skipping {len(all_chunks) - len(texts_to_embed)} cached)...")
            new_embeddings = self.embedder.embed_batch(texts_to_embed)
            
            for idx_pos, chunk_idx in enumerate(indices_needing_emb):
                all_embeddings[chunk_idx] = new_embeddings[idx_pos]
            
            # Store new chunk embeddings in MongoDB for future reuse
            for idx_pos, chunk_idx in enumerate(indices_needing_emb):
                chunk_data = all_chunks[chunk_idx]
                embedding_list = new_embeddings[idx_pos].tolist()
                try:
                    # Look up the original MongoDB document to preserve all fields
                    if chunk_idx < len(existing_chunks):
                        original = existing_chunks[chunk_idx]
                    else:
                        new_idx = chunk_idx - len(existing_chunks)
                        original = new_chunks[new_idx] if new_idx < len(new_chunks) else {}
                    
                    store_fields = {k: v for k, v in original.items() if k != "_id"}
                    store_fields["embedding"] = embedding_list
                    
                    chunks_collection.update_one(
                        {"chunk_id": chunk_data["chunk_id"]},
                        {"$set": store_fields},
                        upsert=True,
                    )
                except Exception:
                    pass
            
            print(f"   💾 Stored embeddings in MongoDB for reuse")
        else:
            print(f"   ✓ All {len(all_chunks)} embeddings loaded from cache")
        
        chunk_embeddings = np.array(all_embeddings, dtype=np.float32)
        print(f"   ✓ Ready with {len(chunk_embeddings)} embeddings")
        
        # Step 10: Hybrid search — BM25 + Cosine fused via RRF
        print(f"   🔍 Hybrid search (BM25 + Cosine → RRF)...")

        from src.retrieval.bm25_index import BM25Index
        from src.retrieval.hybrid_retriever import HybridRetriever

        # --- Semantic (cosine) scoring per-query ---
        semantic_ranked: List[Dict[str, Any]] = []
        chunk_scores = []
        for i, chunk_emb in enumerate(chunk_embeddings):
            max_score = 0
            best_query = ""
            for j, q_emb in enumerate(all_query_embs):
                score = float(np.dot(chunk_emb, q_emb))
                if score > max_score:
                    max_score = score
                    best_query = search_queries[j] if j < len(search_queries) else main_query
            chunk_scores.append({"index": i, "score": max_score, "matched_query": best_query})

        chunk_scores.sort(key=lambda x: x["score"], reverse=True)
        for item in chunk_scores:
            if item["score"] < Config.RETRIEVAL_MIN_SIMILARITY:
                continue
            idx = item["index"]
            chunk = all_chunks[idx]
            paper_id = chunk.get("paper_id")
            paper = unique_papers.get(paper_id, {})
            metadata = chunk.get("metadata") or {
                "title": chunk.get("paper_title") or paper.get("title", ""),
                "year": chunk.get("paper_year") or paper.get("year", ""),
                "section": chunk.get("section", "abstract"),
                "summary": "",
                "tags": [],
                "category": "general",
                "source": paper.get("source", ""),
            }
            semantic_ranked.append({
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
                "metadata": metadata,
            })

        # --- BM25 scoring ---
        bm25_index = BM25Index()
        bm25_index.build_from_chunks(all_chunks)

        # --- Per-query RRF fusion ---
        merged_map: Dict[str, Dict[str, Any]] = {}
        for query in search_queries:
            # BM25 results for this query
            bm25_results = bm25_index.search(query, top_k=Config.BM25_TOP_K)
            # Semantic results matching this query
            query_semantic = [c for c in semantic_ranked if c.get("matched_query") == query]
            # Fuse
            fused = HybridRetriever._rrf_fuse(bm25_results, query_semantic, k=Config.RRF_K)
            for chunk in fused:
                cid = chunk.get("chunk_id")
                if not cid:
                    continue
                chunk["matched_query"] = query
                if cid in merged_map:
                    if chunk.get("rrf_score", 0) > merged_map[cid].get("rrf_score", 0):
                        merged_map[cid] = chunk
                else:
                    merged_map[cid] = chunk

        # Also do a fusion with main_query to catch anything missed
        bm25_main = bm25_index.search(main_query, top_k=Config.BM25_TOP_K)
        main_semantic = [c for c in semantic_ranked if c.get("matched_query") == main_query]
        fused_main = HybridRetriever._rrf_fuse(bm25_main, main_semantic, k=Config.RRF_K)
        for chunk in fused_main:
            cid = chunk.get("chunk_id")
            if not cid:
                continue
            if cid not in merged_map:
                chunk["matched_query"] = main_query
                merged_map[cid] = chunk

        # Sort by RRF score and apply filters
        results = sorted(merged_map.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)

        # Apply metadata and keyword filters post-fusion
        filtered_results = []
        for result in results:
            if metadata_filters and not self._passes_metadata_filters(metadata_filters, result):
                continue
            filtered_results.append(result)

        results = filtered_results[:top_k]

        body_chunks = sum(r.get("section") == "body" for r in results)
        abstract_chunks = sum(r.get("section") == "abstract" for r in results)
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
        
        enhanced_chunks: List[Dict[str, Any]] = []
        for chunk in chunks:
            chunk_query = chunk.get("matched_query") or query
            text = chunk.get("text", "")
            evidence = self.evidence_extractor.select_best_sentence(chunk_query, text)
            enhanced_chunks.append({
                **chunk,
                "evidence_sentence": evidence.get("best_sentence", ""),
                "evidence_score": evidence.get("best_score", 0.0),
                "evidence_below_threshold": evidence.get("below_threshold", False),
            })

        filtered_chunks: List[Dict[str, Any]] = []
        evidence_overlap = max(0, int(Config.EVIDENCE_KEYWORD_MIN_OVERLAP))
        for chunk in enhanced_chunks:
            chunk_query = chunk.get("matched_query") or query
            sentence = chunk.get("evidence_sentence", "")
            target_text = sentence or chunk.get("text", "")
            if not self._passes_domain_gate(chunk_query, target_text):
                continue
            if not self._passes_keyword_filter(chunk_query, target_text, min_overlap=evidence_overlap):
                continue
            filtered_chunks.append(chunk)

        if not filtered_chunks and enhanced_chunks:
            non_below = [c for c in enhanced_chunks if not c.get("evidence_below_threshold")]
            if non_below:
                non_below.sort(key=lambda c: float(c.get("evidence_score", 0) or 0), reverse=True)
                filtered_chunks = non_below[: max(1, min(3, len(non_below)))]

        print(f"   ✓ Extracted evidence from {len(enhanced_chunks)} chunks")
        print(f"   ✓ Retained {len(filtered_chunks)} chunks after evidence-level filtering")
        return filtered_chunks

    @staticmethod
    def _keyword_overlap(query: str, text: str) -> int:
        if not query or not text:
            return 0
        stop_words = {
            "what", "how", "why", "when", "where", "which", "is", "are",
            "does", "do", "can", "the", "a", "an", "in", "of", "and",
            "or", "to", "for", "on", "with", "by", "from", "as", "at",
            "about", "into", "be", "this", "that",
        }
        query_terms = {
            w.strip(".,;:()[]{}\"'`).")
            for w in query.lower().split()
            if w and w not in stop_words and len(w) > 2
        }
        if not query_terms:
            return 0
        text_terms = {
            w.strip(".,;:()[]{}\"'`).")
            for w in text.lower().split()
            if w and w not in stop_words and len(w) > 2
        }
        return len(query_terms.intersection(text_terms))

    def _passes_keyword_filter(self, query: str, text: str, min_overlap: int | None = None) -> bool:
        required_overlap = Config.KEYWORD_MIN_OVERLAP if min_overlap is None else int(min_overlap)
        if required_overlap <= 0:
            return True
        return self._keyword_overlap(query, text) >= required_overlap

    def _passes_domain_gate(self, query: str, text: str) -> bool:
        if not Config.ENABLE_DOMAIN_KEYWORD_GATE or not Config.DOMAIN_KEYWORDS:
            return True

        query_terms = {
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in query.split()
            if w and len(w) > 2
        }
        domain_terms = set(Config.DOMAIN_KEYWORDS)
        if query_terms.isdisjoint(domain_terms):
            return True

        text_terms = {
            w.strip(".,;:()[]{}\"'`).").lower()
            for w in text.split()
            if w and len(w) > 2
        }
        overlap = len(domain_terms.intersection(text_terms))
        return overlap >= Config.DOMAIN_KEYWORD_MIN_OVERLAP

    @staticmethod
    def _passes_metadata_filters(filters: Dict[str, Any] | None, chunk: Dict[str, Any]) -> bool:
        if not filters:
            return True

        metadata = chunk.get("metadata", {}) or {}
        for key, value in filters.items():
            if key == "section":
                section = metadata.get("section") or chunk.get("section")
                if value and section != value:
                    return False
            elif key == "year":
                year = metadata.get("year") or chunk.get("paper_year") or chunk.get("year")
                if isinstance(value, dict):
                    min_year = value.get("min")
                    max_year = value.get("max")
                    if min_year is not None and year and int(year) < int(min_year):
                        return False
                    if max_year is not None and year and int(year) > int(max_year):
                        return False
                elif value is not None and year and str(year) != str(value):
                    return False
            elif key == "tags":
                tags = set(metadata.get("tags", []))
                if isinstance(value, list):
                    if tags.isdisjoint({str(v).lower() for v in value}):
                        return False
                elif value and str(value).lower() not in tags:
                    return False
            elif key == "category":
                category = (metadata.get("category") or "").lower()
                if value and category != str(value).lower():
                    return False
            elif key == "title_contains":
                title = metadata.get("title") or chunk.get("paper_title", "")
                if value and str(value).lower() not in title.lower():
                    return False
            elif key == "source":
                source = metadata.get("source") or ""
                if value and source != value:
                    return False
            else:
                if metadata.get(key) != value:
                    return False
        return True
