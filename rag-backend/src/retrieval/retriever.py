"""Retrieval logic for semantic search and chunk retrieval."""

import numpy as np
from typing import List, Dict, Any, Tuple
from src.embeddings.embedder import get_shared_embedder
from src.vector_store import FAISSVectorStore
from src.database import get_mongo_client
from src.config import Config


class Retriever:
    """Retrieve relevant chunks based on query."""
    
    def __init__(self, use_evidence: bool = False):
        """
        Initialize retriever.
        
        Args:
            use_evidence: If True, enables Stage 2 sentence-level evidence extraction
        """
        self.embedder = get_shared_embedder()
        self.vector_store = FAISSVectorStore()
        self.mongo = get_mongo_client()
        self.use_evidence = use_evidence
        self._evidence_extractor = None
    
    @property
    def evidence_extractor(self):
        """Lazy load evidence extractor only when needed."""
        if self._evidence_extractor is None and self.use_evidence:
            from src.evidence.extractor import EvidenceExtractor
            self._evidence_extractor = EvidenceExtractor()
        return self._evidence_extractor

    @staticmethod
    def _keyword_overlap(query: str, text: str) -> int:
        """Count keyword overlaps between query and text (simple lexical filter)."""
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
        """Return True if query-text keyword overlap meets minimum."""
        required_overlap = Config.KEYWORD_MIN_OVERLAP if min_overlap is None else int(min_overlap)
        if required_overlap <= 0:
            return True
        return self._keyword_overlap(query, text) >= required_overlap

    def _passes_domain_gate(self, query: str, text: str) -> bool:
        """Require domain keyword overlap when enabled and query is domain-specific."""
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
    
    def semantic_retrieve(
        self,
        query: str,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Run FAISS semantic search only — no keyword or domain filtering.

        Designed as a clean input channel for RRF fusion in HybridRetriever.
        Skips keyword overlap filter and domain keyword gate to avoid
        dropping semantically relevant results before fusion.

        Args:
            query: User query string.
            top_k: Number of top results to return.

        Returns:
            List of chunk dicts ranked by cosine similarity, with
            similarity_score field. No keyword/domain filtering applied.
        """
        try:
            query_embedding = self.embedder.embed_text(query)
            distances, indices = self.vector_store.search(query_embedding, top_k)

            chunks_collection = self.mongo.get_chunks_collection()
            papers_collection = self.mongo.get_papers_collection()

            results = []
            for similarity_score, embedding_idx in zip(distances, indices):
                if embedding_idx == -1:
                    continue
                if similarity_score < Config.RETRIEVAL_MIN_SIMILARITY:
                    continue

                chunk = chunks_collection.find_one(
                    {"embedding_index": int(embedding_idx)}
                )
                if not chunk:
                    continue

                paper = papers_collection.find_one(
                    {"paper_id": chunk.get("paper_id")}
                )
                metadata = chunk.get("metadata") or {}
                if not metadata and paper:
                    metadata = {
                        "title": paper.get("title", ""),
                        "year": paper.get("year", ""),
                        "section": chunk.get("section", "abstract"),
                        "summary": "",
                        "tags": [],
                        "category": "general",
                        "source": paper.get("source", ""),
                    }

                results.append({
                    "chunk_id": chunk.get("chunk_id"),
                    "text": chunk.get("text"),
                    "paper_id": chunk.get("paper_id"),
                    "paper_title": (
                        paper.get("title", "Unknown") if paper else "Unknown"
                    ),
                    "paper_year": (
                        paper.get("year", "N/A") if paper else "N/A"
                    ),
                    "similarity_score": float(similarity_score),
                    "section": chunk.get("section", "abstract"),
                    "metadata": metadata,
                })

            return results

        except Exception as e:
            print(f"✗ Error in semantic_retrieve: {e}")
            return []

    def retrieve_chunks(
        self,
        query: str,
        top_k: int = None,
        metadata_filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User query string
            top_k: Number of top chunks to retrieve
            
        Returns:
            List of chunk objects with metadata and similarity scores.
            If use_evidence=True, includes sentence-level evidence.
        """
        if top_k is None:
            top_k = Config.TOP_K
        
        try:
            # Embed query
            query_embedding = self.embedder.embed_text(query)
            
            # Search FAISS
            distances, indices = self.vector_store.search(query_embedding, top_k)
            
            # Retrieve chunks from MongoDB
            chunks_collection = self.mongo.get_chunks_collection()
            papers_collection = self.mongo.get_papers_collection()
            
            results = []
            
            for similarity_score, embedding_idx in zip(distances, indices):
                if embedding_idx == -1:  # Invalid index
                    continue

                if similarity_score < Config.RETRIEVAL_MIN_SIMILARITY:
                    continue
                
                # Find chunk by embedding_index
                chunk = chunks_collection.find_one({"embedding_index": int(embedding_idx)})
                
                if chunk:
                    # Fetch paper metadata
                    paper = papers_collection.find_one({"paper_id": chunk.get("paper_id")})
                    
                    metadata = chunk.get("metadata") or {}
                    if not metadata and paper:
                        metadata = {
                            "title": paper.get("title", ""),
                            "year": paper.get("year", ""),
                            "section": chunk.get("section", "abstract"),
                            "summary": "",
                            "tags": [],
                            "category": "general",
                            "source": paper.get("source", ""),
                        }
                    result = {
                        "chunk_id": chunk.get("chunk_id"),
                        "text": chunk.get("text"),
                        "paper_id": chunk.get("paper_id"),
                        "paper_title": paper.get("title", "Unknown") if paper else "Unknown",
                        "paper_year": paper.get("year", "N/A") if paper else "N/A",
                        "similarity_score": float(similarity_score),
                        "section": chunk.get("section", "abstract"),
                        "metadata": metadata,
                    }
                    if not self._passes_metadata_filters(metadata_filters, result):
                        continue
                    if not self._passes_domain_gate(query, result.get("text", "")):
                        continue
                    if self._passes_keyword_filter(query, result.get("text", "")):
                        results.append(result)
            
            print(f"✓ Retrieved {len(results)} relevant chunks")
            
            # Stage 2: Extract sentence-level evidence if enabled
            if self.use_evidence and results:
                results = self._extract_evidence(query, results)
            
            return results
        
        except Exception as e:
            print(f"✗ Error retrieving chunks: {e}")
            return []
    
    def _extract_evidence(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract sentence-level evidence from chunks (Stage 2).
        
        Args:
            query: The user query
            chunks: Retrieved chunks
            
        Returns:
            Chunks enhanced with evidence_sentence and evidence_score
        """
        if not self.evidence_extractor:
            return chunks

        print("🔍 Extracting sentence-level evidence...")
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

        print(f"✓ Extracted evidence from {len(enhanced_chunks)} chunks")
        print(f"✓ Retained {len(filtered_chunks)} chunks after evidence-level filtering")
        return filtered_chunks
    
    def format_retrieval_results(self, results: List[Dict[str, Any]]) -> str:
        """
        Format retrieval results for display.
        
        Args:
            results: List of retrieved chunks
            
        Returns:
            Formatted string for display
        """
        if not results:
            return "No relevant chunks found."
        
        formatted = "\n" + "="*80 + "\n"
        formatted += "RETRIEVED EVIDENCE\n"
        formatted += "="*80 + "\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"[{i}] {result['paper_title']} ({result['paper_year']})\n"
            formatted += f"    Similarity: {result['similarity_score']:.4f}\n"
            formatted += f"    Text: {result['text'][:150]}...\n\n"
        
        return formatted
    
    def multi_retrieve(
        self, 
        search_queries: List[str], 
        top_k_per_query: int = 5,
        max_total: int = 15,
        metadata_filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks for multiple search queries and merge results.
        
        Stage 3 feature: Given multiple decomposed sub-queries from the planner,
        retrieve relevant chunks for each and return a deduplicated, merged set.
        
        Args:
            search_queries: List of search query strings
            top_k_per_query: Number of chunks to retrieve per query
            max_total: Maximum total chunks to return after merging
            
        Returns:
            Deduplicated list of chunks sorted by best similarity score
        """
        if not search_queries:
            return []
        
        print(f"🔍 Multi-query retrieval for {len(search_queries)} queries...")
        
        # Track chunks by chunk_id for deduplication
        # Store best similarity score for each chunk
        chunks_map: Dict[str, Dict[str, Any]] = {}
        
        for query in search_queries:
            print(f"  → Searching: {query[:60]}...")
            
            try:
                # Embed query
                query_embedding = self.embedder.embed_text(query)
                
                # Search FAISS
                distances, indices = self.vector_store.search(query_embedding, top_k_per_query)
                
                # Retrieve chunks from MongoDB
                chunks_collection = self.mongo.get_chunks_collection()
                papers_collection = self.mongo.get_papers_collection()
                
                for similarity_score, embedding_idx in zip(distances, indices):
                    if embedding_idx == -1:
                        continue

                    if similarity_score < Config.RETRIEVAL_MIN_SIMILARITY:
                        continue
                    
                    chunk = chunks_collection.find_one({"embedding_index": int(embedding_idx)})
                    
                    if chunk:
                        chunk_id = chunk.get("chunk_id")
                        
                        # If we've seen this chunk, keep best score
                        if chunk_id in chunks_map:
                            if similarity_score > chunks_map[chunk_id]["similarity_score"]:
                                chunks_map[chunk_id]["similarity_score"] = float(similarity_score)
                            continue
                        
                        # Fetch paper metadata
                        paper = papers_collection.find_one({"paper_id": chunk.get("paper_id")})
                        
                        metadata = chunk.get("metadata") or {}
                        if not metadata and paper:
                            metadata = {
                                "title": paper.get("title", ""),
                                "year": paper.get("year", ""),
                                "section": chunk.get("section", "abstract"),
                                "summary": "",
                                "tags": [],
                                "category": "general",
                                "source": paper.get("source", ""),
                            }
                        result = {
                            "chunk_id": chunk_id,
                            "text": chunk.get("text"),
                            "paper_id": chunk.get("paper_id"),
                            "paper_title": paper.get("title", "Unknown") if paper else "Unknown",
                            "paper_year": paper.get("year", "N/A") if paper else "N/A",
                            "similarity_score": float(similarity_score),
                            "section": chunk.get("section", "abstract"),
                            "matched_query": query,  # Track which query matched
                            "metadata": metadata,
                        }
                        if not self._passes_metadata_filters(metadata_filters, result):
                            continue
                        if not self._passes_domain_gate(query, result.get("text", "")):
                            continue
                        if self._passes_keyword_filter(query, result.get("text", "")):
                            chunks_map[chunk_id] = result
                        
            except Exception as e:
                print(f"  ⚠ Error searching for query '{query[:30]}...': {e}")
                continue
        
        # Convert to list and sort by similarity score
        results = list(chunks_map.values())
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # Limit to max_total
        results = results[:max_total]
        
        print(f"✓ Multi-retrieve found {len(results)} unique chunks from {len(search_queries)} queries")
        
        # Stage 2: Extract sentence-level evidence if enabled
        if self.use_evidence and results:
            # Use the first query as the main query for evidence extraction
            main_query = search_queries[0] if search_queries else ""
            results = self._extract_evidence(main_query, results)
        
        return results
