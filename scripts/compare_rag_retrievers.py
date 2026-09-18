"""Create the reproducible Step 15-F policy-rule retrieval comparison."""
from __future__ import annotations

import argparse, json, platform, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag import get_retriever
from evals.runner import DEFAULT_RAG_QUERIES, _approved_records, _file_sha256, _load_jsonl, build_rag_report, utc_timestamp

RETRIEVERS = ("keyword-v1", "bm25-v1", "embedding-v1", "hybrid-v1")

def classify_query(row):
    """Derive comparison tags from query-level results, never from query IDs."""
    positive = bool(row["relevant_rule_ids"])
    results = {rid: row[rid] for rid in RETRIEVERS}
    tags = []
    if not positive:
        if all(r.get("negative_success") for r in results.values()): tags.append("negative_correct")
        for rid in RETRIEVERS[1:]:
            if not results[rid].get("negative_success"): tags.append(f"{rid.replace('-v1','')}_negative_regression")
        return tags
    hit = {rid: bool(results[rid].get("hit_at_3")) for rid in RETRIEVERS}
    complete = {rid: results[rid].get("set_recall_at_3") == 1 for rid in RETRIEVERS}
    for rid in RETRIEVERS[1:]:
        if not hit["keyword-v1"] and hit[rid]: tags.append(f"fixed_by_{rid.replace('-v1','')}")
        if hit["keyword-v1"] and not hit[rid]: tags.append(f"{rid.replace('-v1','')}_regression")
        if hit["keyword-v1"] and results["keyword-v1"].get("set_recall_at_3", 0) < 1 and complete[rid]: tags.append(f"completed_by_{rid.replace('-v1','')}")
        if results[rid].get("set_recall_at_3") is not None and results[rid].get("set_recall_at_3") < results["keyword-v1"].get("set_recall_at_3", 0): tags.append(f"{rid.replace('-v1','')}_set_recall_regression")
    if not any(hit.values()): tags.append("still_failed")
    if all(hit.values()): tags.append("all_pass")
    if len(row["relevant_rule_ids"]) > 1:
        partial = [rid for rid in RETRIEVERS if 0 < (results[rid].get("set_recall_at_3") or 0) < 1]
        row["partial_retrievers"] = partial
        if partial: tags.append("multi_rule_partial")
        if all(complete.values()): tags.append("all_complete")
    return tags

def _percent(value):
    return value * 100 if value is not None else None

def _latencies(retriever, queries, repeat):
    if queries: retriever.search(queries[0], top_k=10)
    samples = []
    for query in queries:
        for _ in range(repeat):
            start = time.perf_counter(); retriever.search(query, top_k=10)
            samples.append((time.perf_counter() - start) * 1000)
    ordered = sorted(samples)
    def percentile(p):
        if not ordered: return None
        index = min(len(ordered)-1, max(0, int((len(ordered)-1) * p)))
        return ordered[index]
    return {"mean_ms": statistics.mean(samples) if samples else None,
            "p50_ms": percentile(.50), "p95_ms": percentile(.95),
            "min_ms": min(samples) if samples else None, "max_ms": max(samples) if samples else None,
            "query_count": len(queries), "repeat_count": repeat, "warmup_count": 1}

def _tags(details, all_details, relevant):
    tags=[]; positive=bool(relevant); hit=details["hit_at_3"]
    if not positive and details["negative_success"]: tags.append("negative_correct")
    if positive and hit and details["set_recall_at_3"] < 1: tags.append("multi_rule_partial")
    if positive and not hit: tags.append("still_failed")
    if positive and hit and details["set_recall_at_3"] == 1: tags.append("all_pass")
    return tags

def build_comparison(dataset=DEFAULT_RAG_QUERIES, repeat=5, run_id=None):
    records = _load_jsonl(Path(dataset).resolve()); approved, skipped = _approved_records(records)
    query_texts = [r["input"]["query"] for r in approved]
    reports = {rid: build_rag_report(dataset, run_id=run_id, retriever_id=rid) for rid in RETRIEVERS}
    latency = {rid: _latencies(get_retriever(rid), query_texts, repeat) for rid in RETRIEVERS}
    baseline = reports["keyword-v1"]["metrics"]
    retriever_reports = {}
    for rid in RETRIEVERS:
        report, metrics = reports[rid], reports[rid]["metrics"]
        def rate(name, key="rate"): return metrics[name].get(key)
        item = {"retriever_id": rid, "implementation_id": {"embedding-v1":"sha256-token-hash-512-v1", "hybrid-v1":"rrf-bm25-sha256-hash-v1"}.get(rid, rid),
                "metrics": {"recall_at_1": _percent(rate("recall_at_1")), "recall_at_3": _percent(rate("recall_at_3")), "set_recall_at_3": _percent(rate("set_recall_at_3", "mean")), "mrr": _percent(rate("mrr", "mean")), "negative_no_result_accuracy": _percent(rate("negative_no_result_accuracy", "accuracy"))},
                "zero_result_rate": sum(not q["retrieved_rule_ids"] for q in report["queries"]) / len(report["queries"]), "latency": latency[rid], "query_details": report["queries"]}
        item["identity"] = {"algorithm":"sha256-token-hash","dimension":512,"learned_model":False,"semantic_embedding":False,"external_api":False,"deterministic":True} if rid == "embedding-v1" else None
        if rid == "hybrid-v1": item["fusion"] = {"method":"reciprocal_rank_fusion","rrf_k":60,"components":["bm25-v1","embedding-v1"]}
        baseline_values = {"recall_at_1": baseline["recall_at_1"]["rate"], "recall_at_3": baseline["recall_at_3"]["rate"], "set_recall_at_3": baseline["set_recall_at_3"]["mean"], "mrr": baseline["mrr"]["mean"], "negative_no_result_accuracy": baseline["negative_no_result_accuracy"]["accuracy"]}
        item["deltas_vs_keyword_v1"] = {k: item["metrics"][k] - baseline_values[k] * 100 for k in baseline_values} if rid != "keyword-v1" else None
        retriever_reports[rid] = item
    matrix=[]
    for index, record in enumerate(approved):
        row={"query_id":record["query_id"],"query":record["input"]["query"],"query_type":record.get("tags",[]),"primary_rule_id":record["label"]["candidate_expected"].get("primary_rule_id"),"relevant_rule_ids":record["label"]["candidate_expected"]["relevant_rule_ids"]}
        for rid in RETRIEVERS:
            detail=reports[rid]["queries"][index]; row[rid]={k:detail[k] for k in ("retrieved_rule_ids","hit_at_1","hit_at_3","set_recall_at_3","reciprocal_rank","negative_success")}
        row["comparison_tags"] = classify_query(row)
        row["retrievers"] = {rid: row[rid] for rid in RETRIEVERS}
        matrix.append(row)
    return {"schema_version":"rag-comparison.v1","run_id":run_id,"timestamp_utc":utc_timestamp(),"policy_id":"company-travel-reimbursement","policy_version":"1.0.0","evaluation_scope":"pilot-v1","dataset_path":str(Path(dataset).resolve()),"dataset_sha256":_file_sha256(Path(dataset).resolve()),"approved_queries":len(approved),"skipped_queries":skipped,"python_version":sys.version,"platform":platform.platform(),"repeat_count":repeat,"retrievers":retriever_reports,"query_matrix":matrix}

def markdown(report):
    lines=["# RAG Retriever Comparison", "", f"- Scope: `{report['evaluation_scope']}`", f"- Queries: {report['approved_queries']}", "- Latency: development-machine diagnostic, not a production benchmark", "", "| Retriever | R@1 | R@3 | Set R@3 | MRR | Negative Acc. | Mean ms | p50 ms | p95 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for rid,item in report["retrievers"].items():
        m=item["metrics"]; l=item["latency"]; lines.append(f"| {rid} | {m['recall_at_1']:.2f}% | {m['recall_at_3']:.2f}% | {m['set_recall_at_3']:.2f}% | {m['mrr']:.2f}% | {m['negative_no_result_accuracy']:.2f}% | {l['mean_ms']:.3f} | {l['p50_ms']:.3f} | {l['p95_ms']:.3f} |")
    lines += ["", "## Improvement Summary", ""]
    all_tags = [tag for row in report["query_matrix"] for tag in row["comparison_tags"]]
    for tag in ("fixed_by_bm25","fixed_by_embedding","fixed_by_hybrid","completed_by_bm25","completed_by_embedding","completed_by_hybrid","still_failed","multi_rule_partial","negative_correct"):
        lines.append(f"- {tag}: {all_tags.count(tag)}")
    lines += ["", "## Query-level Comparison", "", "| Query | Keyword | BM25 | Embedding | Hybrid | Tags |", "|---|---|---|---|---|---|"]
    for row in report["query_matrix"]:
        def summary(rid):
            d=row[rid]; return f"hit={d['hit_at_3']}, set={d['set_recall_at_3']}"
        lines.append(f"| {row['query_id']} | {summary('keyword-v1')} | {summary('bm25-v1')} | {summary('embedding-v1')} | {summary('hybrid-v1')} | {', '.join(row['comparison_tags'])} |")
    return "\n".join(lines)+"\n"

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--queries",type=Path,default=DEFAULT_RAG_QUERIES); parser.add_argument("--output",type=Path,default=ROOT/"artifacts/evals/step15v"); parser.add_argument("--repeat",type=int,default=5); args=parser.parse_args()
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); report=build_comparison(args.queries,args.repeat,run_id); args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"rag_comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8"); (args.output/"rag_comparison.md").write_text(markdown(report),encoding="utf8"); print(f"Comparison: {args.output/'rag_comparison.json'}")
if __name__ == "__main__": main()
