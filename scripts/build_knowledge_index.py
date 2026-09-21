import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag import SemanticPolicyRetriever, get_retriever
from app.semantic import BGE_CONFIG, E5_CONFIG, SentenceTransformerEmbedder

MODELS = {
    BGE_CONFIG.model_id: BGE_CONFIG,
    E5_CONFIG.model_id: E5_CONFIG,
}
RETRIEVERS = (
    "keyword-v1", "bm25-v1", "embedding-v1", "hybrid-v1",
    "embedding-v2", "hybrid-v2",
)

parser = argparse.ArgumentParser()
selector = parser.add_mutually_exclusive_group()
selector.add_argument("--retriever", default="embedding-v1", choices=RETRIEVERS)
selector.add_argument("--model", choices=MODELS,
                      help="Build an in-memory candidate semantic index.")
args = parser.parse_args()

if args.model:
    embedder = SentenceTransformerEmbedder(MODELS[args.model], device="cpu")
    retriever = SemanticPolicyRetriever(embedder, f"candidate:{args.model}")
else:
    retriever = get_retriever(args.retriever)

chunks = getattr(retriever, "chunks", getattr(retriever, "rule_chunks", []))
print(f"retriever={retriever.retriever_id}")
print(f"documents indexed={len({c.document_id for c in chunks})}")
print(f"chunks indexed={len(chunks)}")
if hasattr(retriever, "dimensions"):
    print(f"embedding dimension={retriever.dimensions}")
if hasattr(retriever, "index"):
    print(f"model_id={retriever.index.model_id}")
    print(f"model_revision={retriever.index.model_revision}")
    print("corpus=policy-registry")
    print(f"policy_version={retriever.index.policy_version}")
    print(f"dimension={retriever.index.dimension}")
    print(f"model_load_ms={retriever.embedder.model_load_ms:.3f}")
    print(f"embedding/index_build_ms={retriever.index.index_build_ms:.3f}")
    print("index_path=in-memory")
    print("cache_hit=no")
else:
    print("build duration=process-startup index")
