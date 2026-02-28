"""Main entry point with CLI interface."""
import click
import os
from pathlib import Path
from src.database import get_mongo_client
from src.ingestion.loader import PaperIngestor
from src.chunking.processor import TextChunker
from src.embeddings.embedder import EmbeddingGenerator
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
        embedder = EmbeddingGenerator()
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
def query(query, top_k, evidence, plan, dynamic):
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
        if plan:
            _run_agentic_query(query, evidence, mongo, dynamic=dynamic)
            return
        
        # Stage 1/2: Standard retrieval
        retriever = Retriever(use_evidence=evidence)
        retrieved_chunks = retriever.retrieve_chunks(query, top_k)
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


def _run_agentic_query(query: str, use_evidence: bool, mongo, dynamic: bool = False):
    """
    Run Stage 3 agentic RAG flow.
    
    1. PlannerAgent decomposes query into sub-questions
    2. Multi-retrieve chunks for each search query (or dynamic fetch)
    3. Generate grouped answer organized by sub-questions
    
    Args:
        query: User's question
        use_evidence: Enable sentence-level evidence
        mongo: MongoDB client
        dynamic: If True, fetch fresh papers from APIs instead of using indexed data
    """
    from src.llm.factory import get_llm
    from src.agents.planner import PlannerAgent
    
    click.echo("=" * 60)
    if dynamic:
        click.echo("🌐 STAGE 3: AGENTIC RAG + DYNAMIC RETRIEVAL")
    else:
        click.echo("🤖 STAGE 3: AGENTIC RAG")
    click.echo("=" * 60)
    
    # Step 1: Initialize LLM and Planner
    try:
        llm = get_llm()
    except Exception as e:
        click.echo(f"❌ Error initializing LLM: {e}")
        click.echo("   Make sure Ollama is running or GEMINI_API_KEY/GROQ_API_KEY is set.")
        return
    
    planner = PlannerAgent(llm)
    
    # Step 2: Decompose query
    click.echo("\n📋 Step 1: Decomposing query...")
    try:
        plan = planner.plan(query)
    except Exception as e:
        click.echo(f"❌ Error during planning: {e}")
        return
    
    if not plan:
        click.echo("❌ Failed to decompose query.")
        return
    
    click.echo(f"   Main Question: {plan.get('main_question', query)}")
    click.echo(f"   Sub-questions: {len(plan.get('sub_questions', []))}")
    for i, sq in enumerate(plan.get('sub_questions', []), 1):
        click.echo(f"      {i}. {sq}")
    click.echo(f"   Search Queries: {len(plan.get('search_queries', []))}")
    for i, sq in enumerate(plan.get('search_queries', []), 1):
        click.echo(f"      {i}. {sq}")
    
    # Step 3: Retrieve chunks (dynamic or static)
    search_queries = plan.get('search_queries', [query])
    
    if dynamic:
        # Dynamic retrieval: fetch fresh papers from APIs
        click.echo("\n🌐 Step 2: Dynamic paper retrieval...")
        from src.retrieval.dynamic_retriever import DynamicRetriever
        
        dynamic_retriever = DynamicRetriever(use_evidence=True, papers_per_query=5)
        chunks = dynamic_retriever.dynamic_retrieve(
            search_queries=search_queries,
            main_query=query,
            top_k=15
        )
    else:
        # Static retrieval: search pre-indexed FAISS
        click.echo("\n🔍 Step 2: Multi-query retrieval from index...")
        retriever = Retriever(use_evidence=True)
        chunks = retriever.multi_retrieve(
            search_queries,
            top_k_per_query=5,
            max_total=15
        )
    
    if not chunks:
        click.echo("❌ No relevant chunks found for any search query.")
        return
    
    # Step 4: Generate grouped answer
    click.echo("\n📝 Step 3: Generating grouped answer...")
    generator = AnswerGenerator()
    grouped_answer = generator.generate_grouped_answer(plan, chunks)
    
    click.echo(grouped_answer)
    
    # Step 5: Verification (Stage 4)
    click.echo("\n🔍 Step 4: Running verification...")
    from src.agents.verification import VerificationAgent
    
    verifier = VerificationAgent()
    verification_input = verifier.build_verification_input(query, plan, chunks)
    verification_result = verifier.verify(verification_input)
    verification_output = verifier.format_verification_output(verification_result)
    
    click.echo(verification_output)
    
    # Save output
    output_file = "rag_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Query: {query}\n\n")
        if dynamic:
            f.write("Mode: DYNAMIC RETRIEVAL (fresh papers)\n\n")
        f.write(grouped_answer)
        f.write(verification_output)
        f.write(f"\n\nVerification JSON:\n")
        import json
        f.write(json.dumps(verification_result, indent=2))
    click.echo(f"\n✅ Output saved to {output_file}")

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