# RAG v2 retrieval design

The retrieval boundary is `Retriever.search(query, top_k) -> RetrievalResult[]`.
`keyword-v1` remains the frozen legacy baseline and `/rules/search` adapter.
`bm25-v1` is an offline BM25 lexical index with CJK unigram/bigram tokenization.
`embedding-v1` uses a deterministic local hashed-token embedding, so CI and Windows
can run without model downloads; it is an engineering baseline, not a semantic-model
benchmark. `hybrid-v1` combines both rankings with reciprocal rank fusion (k=60).

The corpus is currently projected from the Policy Registry. The same result model
accepts Step 14 `KnowledgeChunk` records, so ingestion and retrieval remain decoupled.
The index is built in memory at process startup; `build_knowledge_index.py` validates
and reports the selected index without rewriting source documents. A future persisted
cache can key embeddings by `(chunk_id, model_id)`.

## Retrieval baseline v1

The sealed comparison scope is the 12-query `rag_pilot.jsonl` Pilot Golden Dataset.
`embedding-v1` is explicitly a deterministic SHA-256 token-hash vector baseline,
not a learned semantic embedding model. The versioned quality summary is
`evals/baselines/rag-retrieval-pilot-v1.json`; latency in generated comparisons is
diagnostic development-machine data, not a production benchmark.
