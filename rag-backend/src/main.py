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
@click.option('--source', default=None, type=click.Choice(['openalex', 'semantic_scholar']), 
              help='Paper source API (default: from config)')
def ingest(query, max_results, source):
    """Ingest papers from OpenAlex or Semantic Scholar API."""
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
def query(query, top_k):
    """Query the RAG system."""
    click.echo(f"\n🔍 Processing query: {query}\n")
    try:
        mongo = get_mongo_client()
        mongo.connect()
        retriever = Retriever()
        retrieved_chunks = retriever.retrieve_chunks(query, top_k)
        if not retrieved_chunks:
            click.echo("❌ No relevant chunks found.")
            return
        click.echo(retriever.format_retrieval_results(retrieved_chunks))
        generator = AnswerGenerator()
        answer = generator.generate_answer(query, retrieved_chunks)
        click.echo(answer)
        final_output = generator.format_final_output(answer, retrieved_chunks)
        output_file = "rag_output.txt"
        with open(output_file, "w") as f:
            f.write(final_output)
        click.echo(f"\n✅ Output saved to {output_file}")
    except Exception as e:
        click.echo(f"❌ Error processing query: {e}")

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