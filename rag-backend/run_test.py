"""Simple test runner for the RAG pipeline."""
import subprocess
import sys

if __name__ == "__main__":
    print("Starting RAG Pipeline Test...")
    print("-" * 40)
    
    # Run the test pipeline
    result = subprocess.run(
        [sys.executable, "-m", "src.test_pipeline"],
        cwd="."
    )
    
    sys.exit(result.returncode)
