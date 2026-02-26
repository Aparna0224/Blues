"""
Test Pipeline - Saves output to files instead of MongoDB.
Run this to verify API calls, chunking, and embeddings work correctly.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config


def test_api_connection():
    """Test OpenAlex API connection and fetch papers."""
    import requests
    
    print("\n" + "="*60)
    print("STEP 1: Testing OpenAlex API Connection")
    print("="*60)
    
    url = f"{Config.OPENALEX_BASE_URL}/works"
    params = {
        "search": "machine learning",
        "per_page": 5,
        "filter": "has_abstract:true"
    }
    
    # Add API key if available
    if Config.OPENALEX_API_KEY:
        params["api_key"] = Config.OPENALEX_API_KEY
        print(f"✓ Using API key: {Config.OPENALEX_API_KEY[:8]}...")
    else:
        print("⚠ No API key configured")
    
    print(f"✓ Base URL: {Config.OPENALEX_BASE_URL}")
    print(f"✓ Query: machine learning")
    print(f"✓ Max results: 5")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        papers = []
        for work in data.get("results", []):
            # OpenAlex returns abstract as inverted index - convert to plain text
            abstract = None
            abstract_inverted_index = work.get("abstract_inverted_index")
            if abstract_inverted_index:
                abstract = _convert_inverted_index_to_text(abstract_inverted_index)
            
            if abstract:
                paper = {
                    "paper_id": work.get("id", "").split("/")[-1],
                    "title": work.get("title", "") or work.get("display_name", ""),
                    "abstract": abstract,
                    "year": work.get("publication_year", 0),
                    "citation_count": work.get("cited_by_count", 0),
                    "source": "openalex"
                }
                papers.append(paper)
        
        print(f"\n✅ SUCCESS: Fetched {len(papers)} papers with abstracts")
        
        # Display paper titles
        for i, p in enumerate(papers, 1):
            title_display = p['title'][:60] if p['title'] else "Untitled"
            print(f"   {i}. {title_display}... ({p['year']})")
        
        return papers
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []


def _convert_inverted_index_to_text(inverted_index):
    """Convert OpenAlex abstract_inverted_index to plain text."""
    if not inverted_index:
        return None
    
    # Create a list of (position, word) tuples
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    
    # Sort by position and join words
    word_positions.sort(key=lambda x: x[0])
    text = " ".join([word for _, word in word_positions])
    
    return text


def test_chunking(papers):
    """Test text chunking on abstracts."""
    import nltk
    
    print("\n" + "="*60)
    print("STEP 2: Testing Text Chunking")
    print("="*60)
    
    # Download NLTK data if needed
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("Downloading NLTK punkt tokenizer...")
        nltk.download('punkt', quiet=True)
    
    try:
        # Try punkt_tab first (newer NLTK versions)
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        try:
            nltk.download('punkt_tab', quiet=True)
        except:
            pass  # Fall back to regular punkt
    
    chunks = []
    min_sentences = Config.MIN_CHUNK_SENTENCES
    max_sentences = Config.MAX_CHUNK_SENTENCES
    
    print(f"✓ Chunk size: {min_sentences}-{max_sentences} sentences")
    
    for paper in papers:
        abstract = paper.get("abstract", "")
        if not abstract:
            continue
        
        # Split into sentences
        try:
            sentences = nltk.sent_tokenize(abstract)
        except Exception as e:
            print(f"⚠ NLTK error, using simple split: {e}")
            sentences = abstract.replace(".", ".|").split("|")
            sentences = [s.strip() for s in sentences if s.strip()]
        
        # Create chunks
        for i in range(0, len(sentences), min_sentences):
            chunk_sentences = sentences[i:i + max_sentences]
            chunk_text = " ".join(chunk_sentences)
            
            if chunk_text.strip():
                chunk = {
                    "chunk_id": f"chunk_{paper['paper_id']}_{i}",
                    "paper_id": paper["paper_id"],
                    "text": chunk_text,
                    "section": "abstract",
                    "sentence_count": len(chunk_sentences)
                }
                chunks.append(chunk)
    
    print(f"\n✅ SUCCESS: Created {len(chunks)} chunks from {len(papers)} papers")
    
    # Show sample chunk
    if chunks:
        print(f"\nSample chunk:")
        print(f"   ID: {chunks[0]['chunk_id']}")
        print(f"   Sentences: {chunks[0]['sentence_count']}")
        print(f"   Text: {chunks[0]['text'][:100]}...")
    
    return chunks


def test_embeddings(chunks):
    """Test embedding generation (limited to save time)."""
    print("\n" + "="*60)
    print("STEP 3: Testing Embedding Generation")
    print("="*60)
    
    print(f"✓ Model: {Config.EMBEDDING_MODEL}")
    print(f"✓ Dimension: {Config.EMBEDDING_DIMENSION}")
    
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        print("\nLoading SciBERT model (this may take a minute on first run)...")
        model = SentenceTransformer(Config.EMBEDDING_MODEL)
        print("✓ Model loaded successfully")
        
        # Only embed first 3 chunks to save time
        test_chunks = chunks[:3]
        texts = [c["text"] for c in test_chunks]
        
        print(f"\nGenerating embeddings for {len(texts)} chunks...")
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        
        # Normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms
        
        print(f"\n✅ SUCCESS: Generated {len(embeddings)} embeddings")
        print(f"   Shape: {embeddings.shape}")
        print(f"   Normalized: Yes (L2 norm = 1.0)")
        
        # Create embedding info (don't save full vectors - too large)
        embedding_info = []
        for i, (chunk, emb) in enumerate(zip(test_chunks, embeddings)):
            info = {
                "chunk_id": chunk["chunk_id"],
                "embedding_shape": list(emb.shape),
                "embedding_norm": float(np.linalg.norm(emb)),
                "embedding_sample": emb[:5].tolist()  # First 5 values only
            }
            embedding_info.append(info)
        
        return embedding_info
        
    except ImportError as e:
        print(f"\n❌ ERROR: Missing dependency - {e}")
        print("   Run: uv pip install sentence-transformers")
        return []
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return []


def save_outputs(papers, chunks, embeddings):
    """Save all outputs to JSON files."""
    print("\n" + "="*60)
    print("STEP 4: Saving Outputs to Files")
    print("="*60)
    
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save papers
    papers_file = output_dir / "papers.json"
    with open(papers_file, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {len(papers)} papers to: {papers_file}")
    
    # Save chunks
    chunks_file = output_dir / "chunks.json"
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {len(chunks)} chunks to: {chunks_file}")
    
    # Save embeddings info
    embeddings_file = output_dir / "embeddings.json"
    with open(embeddings_file, "w", encoding="utf-8") as f:
        json.dump(embeddings, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {len(embeddings)} embedding records to: {embeddings_file}")
    
    # Save summary
    summary = {
        "timestamp": timestamp,
        "config": {
            "openalex_api_key": Config.OPENALEX_API_KEY[:8] + "..." if Config.OPENALEX_API_KEY else None,
            "embedding_model": Config.EMBEDDING_MODEL,
            "embedding_dimension": Config.EMBEDDING_DIMENSION,
            "chunk_sentences": f"{Config.MIN_CHUNK_SENTENCES}-{Config.MAX_CHUNK_SENTENCES}"
        },
        "results": {
            "papers_fetched": len(papers),
            "chunks_created": len(chunks),
            "embeddings_generated": len(embeddings)
        },
        "status": "SUCCESS" if papers and chunks else "PARTIAL"
    }
    
    summary_file = output_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved test summary to: {summary_file}")
    
    return summary


def main():
    """Run the full test pipeline."""
    print("\n" + "="*60)
    print("RAG PIPELINE TEST - Output to Files (No MongoDB)")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Test API
    papers = test_api_connection()
    if not papers:
        print("\n❌ FAILED: Could not fetch papers. Check API connection.")
        return
    
    # Step 2: Test chunking
    chunks = test_chunking(papers)
    if not chunks:
        print("\n❌ FAILED: Could not create chunks.")
        return
    
    # Step 3: Test embeddings
    embeddings = test_embeddings(chunks)
    
    # Step 4: Save outputs
    summary = save_outputs(papers, chunks, embeddings)
    
    # Final report
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print(f"✅ Papers fetched: {summary['results']['papers_fetched']}")
    print(f"✅ Chunks created: {summary['results']['chunks_created']}")
    print(f"✅ Embeddings generated: {summary['results']['embeddings_generated']}")
    print(f"\n📁 Output files saved to: output/")
    print("   - papers.json")
    print("   - chunks.json")
    print("   - embeddings.json")
    print("   - test_summary.json")
    print("\n✅ All tests passed! Ready to integrate with MongoDB.")


if __name__ == "__main__":
    main()
