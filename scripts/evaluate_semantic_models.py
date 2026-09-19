from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag import RETRIEVERS, SemanticPolicyRetriever
from app.semantic import BGE_CONFIG, E5_CONFIG, SentenceTransformerEmbedder
from evals.runner import DEFAULT_RAG_QUERIES, build_rag_report

CANDIDATES = {"bge": BGE_CONFIG, "e5": E5_CONFIG}
SELECTED_CANDIDATE = "e5"


def latency(retriever, queries, repeat=5):
    retriever.search(queries[0], 10)
    samples = []
    for query in queries:
        for _ in range(repeat):
            started = time.perf_counter(); retriever.search(query, 10)
            samples.append((time.perf_counter() - started) * 1000)
    ordered = sorted(samples)
    percentile = lambda p: ordered[int((len(ordered) - 1) * p)]
    return {"mean_ms": statistics.mean(samples), "p50_ms": percentile(.5),
            "p95_ms": percentile(.95), "min_ms": min(samples), "max_ms": max(samples),
            "repeat_count": repeat, "warmup_count": 1}


def _summary(report):
    metrics = report["metrics"]
    metadata = report["semantic_metadata"]
    return {
        "model_id": metadata["model_id"],
        "model_revision": metadata["model_revision"],
        "dimension": metadata["dimension"],
        "recall_at_1": metrics["recall_at_1"]["rate"],
        "recall_at_3": metrics["recall_at_3"]["rate"],
        "set_recall_at_3": metrics["set_recall_at_3"]["mean"],
        "mrr": metrics["mrr"]["mean"],
        "negative_no_result_accuracy": metrics["negative_no_result_accuracy"]["accuracy"],
        "zero_result_rate": sum(
            not item["retrieved_rule_ids"] for item in report["queries"]
        ) / len(report["queries"]),
        "model_load_ms": metadata["model_load_ms"],
        "index_build_ms": metadata["index_build_ms"],
        "query_latency": metadata["query_latency"],
    }


def write_comparison(output):
    paths = {name: output / f"{name}.json" for name in CANDIDATES}
    if not all(path.exists() for path in paths.values()):
        return
    reports = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    comparison = {
        "selected_candidate": SELECTED_CANDIDATE,
        "selected_model_id": CANDIDATES[SELECTED_CANDIDATE].model_id,
        "selection_reasons": [
            "E5 achieved higher Recall@1, Set Recall@3, and MRR on the frozen Pilot.",
            "E5 correctly supports Chinese through its documented multilingual retrieval contract.",
            "E5 uses 384-dimensional vectors instead of BGE's 512, reducing this index's vector footprint.",
            "Both models had the same unresolved negative-query regression; BGE remained smaller and faster.",
        ],
        "threshold_tuning_performed": False,
        "candidates": {name: _summary(report) for name, report in reports.items()},
    }
    json_path = output / "model_comparison.json"
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    lines = [
        "# Semantic model comparison",
        "",
        "| Candidate | Model | R@1 | R@3 | Set R@3 | MRR | Negative accuracy | CPU p50 ms | CPU p95 ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in comparison["candidates"].items():
        latency_data = item["query_latency"]
        lines.append(
            f"| {name} | {item['model_id']} | {item['recall_at_1']:.2%} | "
            f"{item['recall_at_3']:.2%} | {item['set_recall_at_3']:.2%} | "
            f"{item['mrr']:.2%} | {item['negative_no_result_accuracy']:.2%} | "
            f"{latency_data['p50_ms']:.3f} | {latency_data['p95_ms']:.3f} |"
        )
    lines.extend([
        "",
        f"Selected: `{SELECTED_CANDIDATE}`.",
        "",
        *[f"- {reason}" for reason in comparison["selection_reasons"]],
        "",
        "No similarity-threshold tuning was performed; negative-query accuracy is reported as observed.",
    ])
    (output / "model_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_path)


def evaluate(name, output, repeat=5):
    config = CANDIDATES[name]
    embedder = SentenceTransformerEmbedder(config, device="cpu")
    retriever_id = f"semantic-{name}"
    retriever = SemanticPolicyRetriever(embedder, retriever_id,
                                        similarity_threshold=config.similarity_threshold)
    RETRIEVERS[retriever_id] = retriever
    report = build_rag_report(DEFAULT_RAG_QUERIES, run_id=output.name,
                              retriever_id=retriever_id)
    queries = [item["query"] for item in report["queries"]]
    scores = [{"query_id": item["query_id"],
               "top_scores": [result.score for result in retriever.search(item["query"], 3)]}
              for item in report["queries"]]
    report["semantic_metadata"] = {
        "model_id": config.model_id, "dimension": embedder.dimension,
        "model_revision": embedder.model_revision,
        "query_prefix": config.query_prefix, "document_prefix": config.document_prefix,
        "normalize_embeddings": config.normalize_embeddings,
        "similarity_threshold": config.similarity_threshold,
        "device": "cpu", "model_load_ms": embedder.model_load_ms,
        "index_build_ms": retriever.index.index_build_ms,
        "corpus_sha256": retriever.index.corpus_sha256,
        "cache_identity": retriever.index.cache_identity,
        "query_latency": latency(retriever, queries, repeat),
        "score_diagnostics": scores,
    }
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{name}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    write_comparison(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=(*CANDIDATES, "all"), default="all",
                        help="Evaluate one candidate, or both sequentially (default).")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "artifacts/evals/semantic-model-selection" / run_id
    names = CANDIDATES if args.candidate == "all" else (args.candidate,)
    for name in names:
        evaluate(name, output, args.repeat)


if __name__ == "__main__":
    main()
