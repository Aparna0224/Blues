# FILE: src/retrieval/dynamic_retriever.py
"""Dynamic Retriever - Fetches papers on-the-fly with abstract relevance filtering and optional web crawl fallback."""

import asyncio
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional
from src.embeddings.embedder import get_shared_embedder
from src.database import get_mongo_client
from src.ingestion.loader import PaperIngestor
from src.ingestion.fulltext import FullTextFetcher
from src.chunking.processor import TextChunker
from src.config import Config
from src.retrieval.web_crawler import AcademicWebCrawler


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
        
    Fallback:
        - If API chunks < threshold, activate Crawl4AI web fallback.
    """
    
    ABSTRACT_RELEVANCE_THRESHOLD = Config.DYNAMIC_ABSTRACT_MIN_SIMILARITY
    
    def __init__(self, use_evidence: bool = True, papers_per_query: int = 5, source: str | None = None):
        self.embedder = get_shared_embedder()
        self.mongo = get_mongo_client()
        self.ingestor = PaperIngestor(source=source or Config.DEFAULT_PAPER_SOURCE)
        self.fulltext_fetcher = FullTextFetcher()
        self.chunker = TextChunker()
        self.web_crawler = AcademicWebCrawler()
        self.use_evidence = use_evidence
        self.papers_per_query = papers_per_query
        self._evidence_extractor = None
    
    @property
    def evidence_extractor(self):
        if self._evidence_extractor is None and self.use_evidence:
            from src.evidence.extractor import EvidenceExtractor
            self._evidence_extractor = EvidenceExtractor()
        return self._evidence_extractor
    
    async def retrieve(self, search_queries: List[str], use_web_fallback: bool = True, **kwargs) -> List[Dict[str, Any]]:
        print(f"\n🌐 DYNAMIC RETRIEVAL MODE (Parallel)")
        
        main_query = kwargs.get("main_query", search_queries[0] if search_queries else "")
        metadata_filters = kwargs.get("metadata_filters")
        top_k = kwargs.get("top_k", 10)
        
        # 1. Fetch from standard APIs parallel
        api_chunks = await self._fetch_from_apis_parallel(search_queries, main_query)
        
        # 2. Web fallback if chunks are scarce
        threshold = getattr(Config, "MIN_CHUNKS_THRESHOLD", 8)
        if use_web_fallback and getattr(Config, "WEB_CRAWL_ENABLED", True) and len(api_chunks) < threshold:
            print(f"   ⚠️ API Chunks ({len(api_chunks)}) < Threshold ({threshold}). Activating web fallback...")
            web_pages = await asyncio.gather(*[
                self.web_crawler.search_and_crawl(q, n=3)
                for q in search_queries[:3]  # Cap at 3 to control latency
            ])
            web_pages_flat = [p for sublist in web_pages for p in sublist]
            
            web_chunks = await self._process_web_pages(web_pages_flat, search_queries)
            all_chunks = api_chunks + web_chunks
        else:
            all_chunks = api_chunks

        if not all_chunks:
            return []

        # 3. Final embed, score, and filter using existing pipeline
        return await self._embed_score_and_filter(all_chunks, search_queries, main_query, top_k, metadata_filters)

    async def _process_web_pages(self, pages: List[dict], queries: List[str]) -> List[dict]:
        """Convert crawled web pages into chunks using the existing TextChunker."""
        chunks = []
        for page in pages:
            paper_id = hashlib.md5(page["url"].encode()).hexdigest()[:16]
            raw_chunks = self.chunker.chunk(page["content"])
            for i, c in enumerate(raw_chunks):
                chunks.append({
                    "chunk_id": f"web_{paper_id}_{i}",
                    "paper_id": paper_id,
                    "text": c,
                    "title": page.get("title", page["url"]),
                    "paper_title": page.get("title", page["url"]),
                    "source": "web_crawl",
                    "url": page["url"],
                    "section": "full_text",
                    "year": None,
                    "doi": None,
                    "authors": [],
                    "metadata": {}
                })
                
        if chunks:
            # CPU-bound embeddings
            texts = [c["text"] for c in chunks]
            embeddings = await asyncio.to_thread(self.embedder.embed_batch, texts)
            for c, emb in zip(chunks, embeddings):
                c["embedding"] = emb.tolist() if hasattr(emb, "tolist") else emb
                
        return chunks

    async def _fetch_from_apis_parallel(self, search_queries: List[str], main_query: str) -> List[Dict[str, Any]]:
        self.mongo.connect()
        papers_collection = self.mongo.get_papers_collection()
        chunks_collection = self.mongo.get_chunks_collection()
        
        print(f"\n📋 STAGE A: Abstract Relevance Filtering")
        
        # Parallel ingestion
        async def fetch_q(q):
            try:
                return await asyncio.to_thread(self.ingestor.fetch_papers, q, max_results=self.papers_per_query)
            except Exception as e:
                print(f"     ⚠ Error fetching {q}: {e}")
                return []
                
        results = await asyncio.gather(*[fetch_q(q) for q in search_queries])
        all_papers = [p for sublist in results if sublist for p in sublist]
        
        if not all_papers:
            return []

        unique_papers = {}
        for p in all_papers:
            pid = p.get("paper_id")
            if pid and pid not in unique_papers:
                unique_papers[pid] = p

        existing_paper_ids = []
        new_paper_ids = []
        for pid, paper in unique_papers.items():
            existing = await asyncio.to_thread(papers_collection.find_one, {"paper_id": pid})
            if existing:
                existing_paper_ids.append(pid)
                if existing.get("full_text"):
                    unique_papers[pid]["full_text"] = existing["full_text"]
            else:
                new_paper_ids.append(pid)

        # Hybrid Abstract scoring
        from rank_bm25 import BM25Okapi
        import re as _re
        def _bm25_tokenize(text: str) -> list:
            return [w for w in _re.findall(r'[a-z0-9]+', (text or "").lower()) if len(w) > 1]
            
        def embed_q(q): return self.embedder.embed_text(q)
        query_emb = await asyncio.to_thread(embed_q, main_query)
        search_embs = await asyncio.to_thread(lambda: [self.embedder.embed_text(sq) for sq in search_queries])
        all_query_embs = search_embs + [query_emb]

        abstract_texts = []
        abstract_pids = []
        for pid, paper in unique_papers.items():
            abstract = paper.get("abstract", "")
            if abstract:
                abstract_texts.append(abstract)
                abstract_pids.append(pid)

        tokenized_abstracts = [_bm25_tokenize(a) for a in abstract_texts]
        bm25_abstract = await asyncio.to_thread(BM25Okapi, tokenized_abstracts) if tokenized_abstracts else None
        
        bm25_abstract_scores = {}
        if bm25_abstract and abstract_pids:
            for sq in search_queries + [main_query]:
                raw_scores = bm25_abstract.get_scores(_bm25_tokenize(sq))
                max_raw = max(raw_scores) + 1e-9
                for idx, pid in enumerate(abstract_pids):
                    normalized = float(raw_scores[idx]) / max_raw
                    bm25_abstract_scores[pid] = max(bm25_abstract_scores.get(pid, 0.0), normalized)

        relevant_papers = []
        bm25_weight = getattr(Config, "ABSTRACT_HYBRID_BM25_WEIGHT", 0.4)
        semantic_weight = getattr(Config, "ABSTRACT_HYBRID_SEMANTIC_WEIGHT", 0.6)
        
        for pid, paper in unique_papers.items():
            abstract = paper.get("abstract", "")
            if not abstract:
                continue
            abstract_emb = await asyncio.to_thread(self.embedder.embed_text, abstract)
            cosine_score = max(float(np.dot(abstract_emb, qe)) for qe in all_query_embs)
            bm25_score = bm25_abstract_scores.get(pid, 0.0)
            
            hybrid_abstract_score = (semantic_weight * cosine_score) + (bm25_weight * bm25_score)
            paper["_abstract_relevance"] = hybrid_abstract_score
            
            if hybrid_abstract_score >= self.ABSTRACT_RELEVANCE_THRESHOLD:
                relevant_papers.append(paper)
                
        relevant_papers.sort(key=lambda p: p.get("_abstract_relevance", 0), reverse=True)

        if not relevant_papers:
            return []

        # Stage B
        print(f"\n📖 STAGE B: Full-Text Fetch & Chunking")
        
        async def fetch_full(p):
            if not p.get("full_text"):
                has_oa = p.get("full_text_url") or p.get("best_oa_pdf_url") or p.get("oa_url")
                if has_oa:
                    ft = await asyncio.to_thread(self.fulltext_fetcher.fetch_full_text, p)
                    if ft:
                        p["full_text"] = ft
        
        await asyncio.gather(*[fetch_full(p) for p in relevant_papers])

        relevant_pids = {p["paper_id"] for p in relevant_papers}
        reuse_ids = []
        for pid in existing_paper_ids:
            if pid in relevant_pids:
                has_chunks = await asyncio.to_thread(chunks_collection.count_documents, {"paper_id": pid}, limit=1)
                has_new_fulltext = unique_papers.get(pid, {}).get("full_text") and not await asyncio.to_thread(chunks_collection.find_one, {"paper_id": pid, "section": "body"})
                if has_chunks and not has_new_fulltext:
                    reuse_ids.append(pid)

        existing_chunks = []
        if reuse_ids:
            cursor = chunks_collection.find({"paper_id": {"$in": reuse_ids}})
            existing_chunks = await asyncio.to_thread(lambda: list(cursor))

        papers_to_chunk = [p for p in relevant_papers if p.get("paper_id") not in reuse_ids]
        new_chunks = []
        if papers_to_chunk:
            new_chunks = await asyncio.to_thread(self.chunker.create_chunks, papers_to_chunk)
            # Store chunks asynchronously
            async def store_p(p):
                store_paper = {k: v for k, v in p.items() if not k.startswith("_")}
                await asyncio.to_thread(papers_collection.update_one, {"paper_id": store_paper["paper_id"]}, {"$set": store_paper}, upsert=True)
            await asyncio.gather(*[store_p(p) for p in papers_to_chunk])

        all_chunks = []
        for chunk in existing_chunks:
            paper = unique_papers.get(chunk.get("paper_id"), {})
            entry = {**chunk, "paper_title": paper.get("title", "Unknown"), "source": "existing"}
            all_chunks.append(entry)
            
        for chunk in new_chunks:
            paper = unique_papers.get(chunk.get("paper_id"), {})
            entry = {**chunk, "paper_title": paper.get("title", "Unknown"), "source": "new"}
            # Need to embed new ones
            all_chunks.append(entry)

        # Batch embed anything missing embedding
        needs_emb = [i for i, c in enumerate(all_chunks) if not c.get("embedding")]
        if needs_emb:
            texts = [all_chunks[i]["text"] for i in needs_emb]
            embs = await asyncio.to_thread(self.embedder.embed_batch, texts)
            for i, emb in zip(needs_emb, embs):
                all_chunks[i]["embedding"] = emb.tolist() if hasattr(emb, "tolist") else emb

        return all_chunks

    async def _embed_score_and_filter(self, all_chunks: List[dict], search_queries: List[str], main_query: str, top_k: int, metadata_filters: dict) -> List[dict]:
        """Hybrid sort, evidence extract."""
        print(f"   🔍 Hybrid search on {len(all_chunks)} chunks...")
        if not all_chunks:
            return []

        search_embs = await asyncio.to_thread(lambda: [self.embedder.embed_text(q) for q in search_queries])
        query_emb = await asyncio.to_thread(self.embedder.embed_text, main_query)
        all_query_embs = search_embs + [query_emb]
        
        # Parallel semantic loop
        def score_sem(chunk):
            chunk_emb = np.array(chunk.get("embedding", []), dtype=np.float32)
            if chunk_emb.size == 0:
                return {"score": 0.0, "query": main_query}
            scores = [float(np.dot(chunk_emb, qe)) for qe in all_query_embs]
            idx = np.argmax(scores)
            return {"score": scores[idx], "query": search_queries[idx] if idx < len(search_queries) else main_query}
            
        sem_results = await asyncio.to_thread(lambda: [score_sem(c) for c in all_chunks])
        for i, res in enumerate(sem_results):
            all_chunks[i]["similarity_score"] = res["score"]
            all_chunks[i]["matched_query"] = res["query"]

        from src.retrieval.bm25_index import BM25Index
        from src.retrieval.reranker import GlobalReranker
        
        bm25_index = BM25Index()
        await asyncio.to_thread(bm25_index.build_from_chunks, all_chunks)
        
        merged_map = {}
        k_val = getattr(Config, "RRF_K", 60)
        
        for q in search_queries + [main_query]:
            bm25_res = await asyncio.to_thread(bm25_index.search, q, getattr(Config, "BM25_TOP_K", 50))
            q_sem = [c for c in all_chunks if c.get("matched_query") == q]
            fused = GlobalReranker.global_rerank(bm25_res, q_sem, [q])
            for c in fused:
                cid = c.get("chunk_id")
                if not cid: continue
                c["matched_query"] = q
                if cid not in merged_map or c.get("rrf_score", 0) > merged_map[cid].get("rrf_score", 0):
                    merged_map[cid] = c

        results = sorted(merged_map.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)

        if metadata_filters:
            results = [r for r in results if self._passes_metadata_filters(metadata_filters, r)]
            
        results = results[:top_k]

        if self.use_evidence and results:
            def ext_ev(res): return [self._extract_evidence_single(main_query, r) for r in res]
            results = await asyncio.to_thread(ext_ev, results)

        return results
        
    def _extract_evidence_single(self, query: str, chunk: dict) -> dict:
        if not self.evidence_extractor:
            return chunk
        evidence = self.evidence_extractor.select_best_sentence(chunk.get("matched_query", query), chunk.get("text", ""))
        return {
            **chunk,
            "evidence_sentence": evidence.get("best_sentence", ""),
            "evidence_score": evidence.get("best_score", 0.0)
        }

    @staticmethod
    def _passes_metadata_filters(filters: Dict[str, Any] | None, chunk: Dict[str, Any]) -> bool:
        if not filters:
            return True
        metadata = chunk.get("metadata", {}) or {}
        for key, value in filters.items():
            if key == "source":
                if metadata.get("source") != value and chunk.get("source") != value:
                    return False
        return True
