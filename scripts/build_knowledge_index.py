import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag import get_retriever

parser = argparse.ArgumentParser()
parser.add_argument("--retriever", default="embedding-v1", choices=("keyword-v1", "bm25-v1", "embedding-v1", "hybrid-v1"))
args = parser.parse_args()
retriever = get_retriever(args.retriever)
chunks = getattr(retriever, "chunks", getattr(retriever, "rule_chunks", []))
print(f"retriever={retriever.retriever_id}")
print(f"documents indexed={len({c.document_id for c in chunks})}")
print(f"chunks indexed={len(chunks)}")
if hasattr(retriever, "dimensions"): print(f"embedding dimension={retriever.dimensions}")
print("build duration=process-startup index")
