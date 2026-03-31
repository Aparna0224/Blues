"""Main entry point with CLI interface."""
import click
import os
from pathlib import Path
from src.database import get_mongo_client
from src.ingestion.loader import PaperIngestor
from src.chunking.processor import TextChunker
from src.embeddings.embedder import EmbeddingGenerator, get_shared_embedder
from src.vector_store import FAISSVectorStore
from src.retrieval.retriever import Retriever
from src.generation.generator import AnswerGenerator
from src.config import Config

@click.group()
def cli():
    """RAG System CLI - Stage 1 (No Agents)"""
    pass

@cli.command()
@click.option('--query', prompt='Enter search query', help='Search query for papers')
@click.option('--max-results', default=10, help='Maximum papers to fetch')
@click.option('--source', default=None, type=click.Choice(['openalex', 'semantic_scholar', 'both']), 
              help='Paper source API (default: from config, use "both" for dual API)')
def ingest(query, max_results, source):
    """Ingest papers from OpenAlex, Semantic Scholar, or both APIs."""
    source_name = source or Config.DEFAULT_PAPER_SOURCE
    click.echo(f"\n📚 Starting ingestion for: {query}")
    click.echo(f"   Source: {source_name}")
    try:
        mongo = get_mongo_client()
        mongo.connect()
        ingestor = PaperIngestor(source=source)
        papers = ingestor.fetch_papers(query, max_results)
        if not papers:
            click.echo("❌ No papers found.")
            return
        inserted = ingestor.insert_papers(papers)
        click.echo(f"✅ Ingested {inserted} papers")
    except Exception as e:
        click.echo(f"❌ Error during ingestion: {e}")

@cli.command()
def build_index():
    """Build FAISS index from ingested papers."""
    click.echo("\n🔨 Building FAISS index...")
    try:
        mongo = get_mongo_client()
        mongo.connect()
        papers_collection = mongo.get_papers_collection()
        papers = list(papers_collection.find().limit(100))
        if not papers:
            click.echo("❌ No papers in database. Run 'ingest' first.")
            return
        click.echo(f"📄 Found {len(papers)} papers")
        chunker = TextChunker()
        chunks = chunker.create_chunks(papers)
        click.echo(f"📝 Created {len(chunks)} chunks")
        embedder = get_shared_embedder()
        embeddings, chunks = embedder.generate_chunk_embeddings(chunks)
        click.echo(f"✨ Generated {len(embeddings)} embeddings")
        vector_store = FAISSVectorStore()
        embedding_indices = vector_store.add_embeddings(
            embeddings,
            [c.get("chunk_id") for c in chunks]
        )
        chunks_collection = mongo.get_chunks_collection()
        for chunk, emb_idx in zip(chunks, embedding_indices):
            chunks_collection.insert_one(chunk)
            chunks_collection.update_one(
                {"chunk_id": chunk.get("chunk_id")},
                {"$set": {"embedding_index": emb_idx}}
            )
        vector_store.save_index()
        click.echo(f"✅ Index built with {vector_store.get_index_size()} vectors")
    except Exception as e:
        click.echo(f"❌ Error building index: {e}")

@cli.command()
@click.option('--query', prompt='Enter your question', help='Query to answer')
@click.option('--top-k', default=5, help='Number of chunks to retrieve')
@click.option('--evidence', is_flag=True, default=False, 
              help='Enable Stage 2 sentence-level evidence extraction')
@click.option('--plan', is_flag=True, default=False,
              help='Enable Stage 3 agentic planning with query decomposition')
@click.option('--dynamic', is_flag=True, default=False,
              help='Enable dynamic paper fetching (fetch fresh papers for each query)')
@click.option('--filter-section', default=None, help='Filter by section (abstract/body)')
@click.option('--filter-category', default=None, help='Filter by chunk category')
@click.option('--filter-tags', default=None, help='Comma-separated tags to match')
@click.option('--filter-year-min', default=None, type=int, help='Minimum publication year')
@click.option('--filter-year-max', default=None, type=int, help='Maximum publication year')
@click.option('--filter-title-contains', default=None, help='Filter by title substring')
@click.option('--filter-source', default=None, help='Filter by source (openalex/semantic_scholar)')
def query(
    query,
    top_k,
    evidence,
    plan,
    dynamic,
    filter_section,
    filter_category,
    filter_tags,
    filter_year_min,
    filter_year_max,
    filter_title_contains,
    filter_source,
):
    """Query the RAG system."""
    click.echo(f"\n🔍 Processing query: {query}")
    if dynamic:
        click.echo("   🌐 Dynamic retrieval: ENABLED (fetching fresh papers)")
    if plan:
        click.echo("   🤖 Agentic planning: ENABLED")
        click.echo(f"   📝 Sentence-level evidence: {'ENABLED' if evidence else 'AUTO'}\n")
    elif evidence:
        click.echo("   📝 Sentence-level evidence: ENABLED\n")
    else:
        click.echo("")
    
    try:
        mongo = get_mongo_client()
        mongo.connect()
        
        # Stage 3: Agentic RAG with planning (with optional dynamic retrieval)
        filters = _build_metadata_filters(
            section=filter_section,
            category=filter_category,
            tags=filter_tags,
            year_min=filter_year_min,
            year_max=filter_year_max,
            title_contains=filter_title_contains,
            source=filter_source,
        )

        if plan:
            _run_agentic_query(query, evidence, mongo, dynamic=dynamic, metadata_filters=filters)
            return
        
        # Stage 1/2: Standard retrieval
        retriever = Retriever(use_evidence=evidence)
        retrieved_chunks = retriever.retrieve_chunks(query, top_k, metadata_filters=filters)
        if not retrieved_chunks:
            click.echo("❌ No relevant chunks found.")
            return
        
        # Format output based on evidence mode
        if evidence:
            # Stage 2: Show sentence-level evidence
            from src.evidence.extractor import EvidenceExtractor
            extractor = EvidenceExtractor()
            click.echo(extractor.format_evidence_output(retrieved_chunks))
        else:
            click.echo(retriever.format_retrieval_results(retrieved_chunks))
        
        generator = AnswerGenerator()
        answer = generator.generate_answer(query, retrieved_chunks)
        click.echo(answer)
        final_output = generator.format_final_output(answer, retrieved_chunks)
        output_file = "rag_output.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_output)
        click.echo(f"\n✅ Output saved to {output_file}")
    except Exception as e:
        click.echo(f"❌ Error processing query: {e}")


def _build_metadata_filters(
    section: str | None = None,
    category: str | None = None,
    tags: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    title_contains: str | None = None,
    source: str | None = None,
) -> dict | None:
    filters: dict[str, object] = {}

    if section:
        filters["section"] = section
    if category:
        filters["category"] = category
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            filters["tags"] = tag_list
    if year_min is not None or year_max is not None:
        year_filter: dict[str, int] = {}
        if year_min is not None:
            year_filter["min"] = year_min
        if year_max is not None:
            year_filter["max"] = year_max
        if year_filter:
            filters["year"] = year_filter
    if title_contains:
        filters["title_contains"] = title_contains
    if source:
        filters["source"] = source

    return filters or None


def _run_agentic_query(
    query: str,
    use_evidence: bool,
    mongo,
    dynamic: bool = False,
    metadata_filters: dict | None = None,
):
    """
    Run Stage 3 agentic RAG flow with Stage 4 verification,
    Stage 5 execution trace, and LLM research summary.
    
    1. PlannerAgent decomposes query into sub-questions
    2. Multi-retrieve chunks for each search query (or dynamic fetch)
    3. Generate grouped answer organized by sub-questions
    4. VerificationAgent scores confidence
    5. ExecutionTracer captures full trace → JSON + MongoDB
    6. PipelineSummarizer produces LLM narrative → appended to output
    
    Args:
        query: User's question
        use_evidence: Enable sentence-level evidence
        mongo: MongoDB client
        dynamic: If True, fetch fresh papers from APIs instead of using indexed data
    """
    import json
    import time as _time
    from src.llm.factory import get_llm
    from src.agents.planner import PlannerAgent
    from src.agents.verification import VerificationAgent
    from src.trace.tracer import ExecutionTracer
    from src.generation.summarizer import PipelineSummarizer
    
    mode = "dynamic" if dynamic else "cached"
    tracer = ExecutionTracer(query=query, mode=mode)
    
    click.echo("=" * 60)
    if dynamic:
        click.echo("🌐 STAGE 3: AGENTIC RAG + DYNAMIC RETRIEVAL")
    else:
        click.echo("🤖 STAGE 3: AGENTIC RAG")
    click.echo("=" * 60)
    
    # ── Step 1: Initialize LLM and Planner ───────────────────────
    try:
        llm = get_llm()
    except Exception as e:
        click.echo(f"❌ Error initializing LLM: {e}")
        click.echo("   Make sure Ollama is running or GEMINI_API_KEY/GROQ_API_KEY is set.")
        tracer.record_error("initialization", e)
        tracer.mark_failed()
        _save_trace(tracer, mongo)
        return
    
    planner = PlannerAgent(llm)
    
    # ── Step 2: Decompose query ──────────────────────────────────
    click.echo("\n📋 Step 1: Decomposing query...")
    plan = None
    try:
        t0 = _time.perf_counter()
        plan = planner.plan(query)
        planning_ms = round((_time.perf_counter() - t0) * 1000, 1)
    except Exception as e:
        click.echo(f"❌ Error during planning: {e}")
        tracer.record_error("planning", e)
        tracer.mark_failed()
        _save_trace(tracer, mongo)
        return
    
    if not plan:
        click.echo("❌ Failed to decompose query.")
        tracer.record_error("planning", RuntimeError("Empty plan returned"))
        tracer.mark_failed()
        _save_trace(tracer, mongo)
        return
    
    sub_questions = plan.get('sub_questions', [])
    search_queries = plan.get('search_queries', [query])
    
    tracer.record_planning(
        input_question=query,
        sub_questions=sub_questions,
        search_queries=search_queries,
        llm_raw_output=plan.get('_raw_output', ''),
        latency_ms=planning_ms,
    )
    
    click.echo(f"   Main Question: {plan.get('main_question', query)}")
    click.echo(f"   Sub-questions: {len(sub_questions)}")
    for i, sq in enumerate(sub_questions, 1):
        click.echo(f"      {i}. {sq}")
    click.echo(f"   Search Queries: {len(search_queries)}")
    for i, sq in enumerate(search_queries, 1):
        click.echo(f"      {i}. {sq}")
    
    # ── Step 3: Retrieve chunks ──────────────────────────────────
    chunks = []
    try:
        if dynamic:
            click.echo("\n🌐 Step 2: Dynamic paper retrieval...")
            from src.retrieval.dynamic_retriever import DynamicRetriever
            
            dynamic_retriever = DynamicRetriever(use_evidence=True, papers_per_query=5)
            chunks = dynamic_retriever.dynamic_retrieve(
                search_queries=search_queries,
                main_query=query,
                top_k=15,
                metadata_filters=metadata_filters,
            )
        else:
            click.echo("\n🔍 Step 2: Multi-query retrieval from index...")
            retriever = Retriever(use_evidence=True)
            chunks = retriever.multi_retrieve(
                search_queries,
                top_k_per_query=5,
                max_total=15,
                metadata_filters=metadata_filters,
            )
    except Exception as e:
        click.echo(f"❌ Error during retrieval: {e}")
        tracer.record_error("retrieval", e)
        tracer.mark_failed()
        _save_trace(tracer, mongo)
        return
    
    if not chunks:
        click.echo("❌ No relevant chunks found for any search query.")
        tracer.record_error("retrieval", RuntimeError("No chunks returned"))
        tracer.mark_failed()
        _save_trace(tracer, mongo)
        return
    
    # Build per-query retrieval trace
    per_query_trace = []
    for sq in search_queries:
        matching = [
            c for c in chunks
            if c.get("search_query") == sq or True  # all chunks available
        ]
        per_query_trace.append({
            "search_query": sq,
            "top_k": 15,
            "retrieved_chunk_ids": [c.get("chunk_id", "") for c in matching[:5]],
            "similarity_scores": [c.get("similarity_score", 0) for c in matching[:5]],
        })
    
    tracer.record_retrieval(
        per_query=per_query_trace,
        total_chunks_before_merge=len(chunks),
        unique_chunks_after_merge=len({c.get("chunk_id", i) for i, c in enumerate(chunks)}),
    )
    
    # ── Step 4: Generate grouped answer ──────────────────────────
    click.echo("\n📝 Step 3: Generating grouped answer...")
    try:
        generator = AnswerGenerator()
        grouped_answer = generator.generate_grouped_answer(plan, chunks)
    except Exception as e:
        click.echo(f"❌ Error generating answer: {e}")
        tracer.record_error("evidence_selection", e)
        tracer.mark_failed()
        _save_trace(tracer, mongo)
        return
    
    click.echo(grouped_answer)
    
    # Record evidence selection from chunks
    tracer.record_evidence_selection(
        claims_used=[
            {
                "chunk_id": c.get("chunk_id", ""),
                "claim": c.get("evidence_sentence", c.get("text", "")[:200]),
                "similarity_score": c.get("similarity_score", 0),
                "paper_id": c.get("paper_id", ""),
                "sub_question": "",
            }
            for c in chunks
        ]
    )
    
    # ── Step 5: Verification (Stage 4) ───────────────────────────
    click.echo("\n🔍 Step 4: Running verification...")
    verification_result = None
    verification_output = ""
    try:
        verifier = VerificationAgent()
        verification_input = verifier.build_verification_input(query, plan, chunks)
        verification_result = verifier.verify(verification_input)
        verification_output = verifier.format_verification_output(verification_result)
    except Exception as e:
        click.echo(f"❌ Error during verification: {e}")
        tracer.record_error("verification", e)
    
    if verification_result:
        tracer.record_verification(verification_result)
        
        # Record filtering from verification audit
        audit = verification_result.get("audit", {})
        tracer.record_filtering(
            total_claims_received=audit.get("total_claims_received", 0),
            after_deduplication=audit.get("claims_after_dedup", 0),
            after_relevance_filter=audit.get("claims_after_relevance_filter", 0),
            above_similarity_threshold=audit.get("claims_above_similarity_threshold", 0),
            claims_rejected=audit.get("claims_rejected", 0),
        )
    
    click.echo(verification_output)
    
    # ── Step 6: LLM Research Summary (Stage 5) ───────────────────
    click.echo("\n📝 Step 5: Generating research summary...")
    summary_output = ""
    try:
        summarizer = PipelineSummarizer(llm)
        summary_output = summarizer.summarize(
            grouped_answer=grouped_answer,
            verification_output=verification_output,
            verification_result=verification_result,
        )
        click.echo(summary_output)
    except Exception as e:
        click.echo(f"⚠ Summary generation failed: {e}")
        tracer.record_error("summary", e)
    
    # ── Save output (Stage 4 + summary appended) ─────────────────
    output_file = "rag_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Query: {query}\n\n")
        if dynamic:
            f.write("Mode: DYNAMIC RETRIEVAL (fresh papers)\n\n")
        f.write(grouped_answer)
        f.write(verification_output)
        f.write(f"\n\nVerification JSON:\n")
        json.dump(verification_result, f, indent=2)
        # Append LLM summary at the end
        if summary_output:
            f.write("\n")
            f.write(summary_output)
    click.echo(f"\n✅ Output saved to {output_file}")
    
    # ── Save trace (separate file + MongoDB) ─────────────────────
    _save_trace(tracer, mongo)


def _save_trace(tracer, mongo) -> None:
    """Finalize trace, save to JSON file and MongoDB."""
    import json
    
    try:
        trace_path = tracer.save_trace(directory="output")
        click.echo(f"📋 Trace saved to {trace_path}")
    except Exception as e:
        click.echo(f"⚠ Failed to save trace file: {e}")
    
    try:
        trace = tracer.finalize()
        execution_id = mongo.store_trace(trace)
        click.echo(f"📋 Trace stored in MongoDB (execution_id: {execution_id})")
    except Exception as e:
        click.echo(f"⚠ Failed to store trace in MongoDB: {e}")

@cli.command()
def status():
    """Check RAG system status."""
    click.echo("\n📊 RAG System Status\n")
    try:
        mongo = get_mongo_client()
        mongo.connect()
        papers_count = mongo.get_papers_collection().count_documents({})
        chunks_count = mongo.get_chunks_collection().count_documents({})
        click.echo(f"✅ MongoDB connected")
        click.echo(f"   Papers: {papers_count}")
        click.echo(f"   Chunks: {chunks_count}")
        vector_store = FAISSVectorStore()
        index_size = vector_store.get_index_size()
        click.echo(f"\n✅ FAISS Index")
        click.echo(f"   Vectors: {index_size}")
        click.echo(f"   Path: {Config.FAISS_INDEX_PATH}")
        
        # Show API configuration status
        click.echo(f"\n🔑 API Configuration")
        if Config.OPENALEX_API_KEY:
            click.echo(f"   OpenAlex: Configured (100k credits/day)")
        else:
            click.echo(f"   OpenAlex: No API key (100 credits/day)")
        if Config.SEMANTIC_SCHOLAR_API_KEY:
            click.echo(f"   Semantic Scholar: Configured")
        else:
            click.echo(f"   Semantic Scholar: No API key")
        click.echo(f"   Default Source: {Config.DEFAULT_PAPER_SOURCE}")
        
        # Show LLM configuration status (Stage 3)
        click.echo(f"\n🤖 LLM Configuration (Stage 3)")
        click.echo(f"   Provider: {Config.LLM_PROVIDER}")
        if Config.LLM_PROVIDER == "local":
            click.echo(f"   Model: {Config.OLLAMA_MODEL}")
            click.echo(f"   Base URL: {Config.OLLAMA_BASE_URL}")
        elif Config.LLM_PROVIDER == "gemini":
            if Config.GEMINI_API_KEY:
                click.echo(f"   Model: {Config.GEMINI_MODEL}")
                click.echo(f"   API Key: ****{Config.GEMINI_API_KEY[-4:]}")
            else:
                click.echo(f"   ⚠️ GEMINI_API_KEY not set")
        elif Config.LLM_PROVIDER == "groq":
            if Config.GROQ_API_KEY:
                click.echo(f"   Model: {Config.GROQ_MODEL}")
                click.echo(f"   API Key: ****{Config.GROQ_API_KEY[-4:]}")
            else:
                click.echo(f"   ⚠️ GROQ_API_KEY not set")
        click.echo(f"   Temperature: {Config.LLM_TEMPERATURE}")
    except Exception as e:
        click.echo(f"❌ Error checking status: {e}")

@cli.command()
def reset():
    """Reset all data (USE WITH CAUTION)."""
    if click.confirm("⚠️  This will delete all papers, chunks, and the FAISS index. Continue?"):
        try:
            mongo = get_mongo_client()
            mongo.connect()
            mongo.get_papers_collection().delete_many({})
            mongo.get_chunks_collection().delete_many({})
            if os.path.exists(Config.FAISS_INDEX_PATH):
                os.remove(Config.FAISS_INDEX_PATH)
            click.echo("✅ Reset complete")
        except Exception as e:
            click.echo(f"❌ Error during reset: {e}")
    else:
        click.echo("Reset cancelled")

if __name__ == "__main__":
    cli()