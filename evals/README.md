# Evaluation Contracts and Pilot Datasets

This directory contains human-reviewed evaluation assets and the baseline
evaluation runner for policy version `1.0.0`.

## Pilot Golden Dataset Status

- Status: `APPROVED`
- Audit cases: 12
- RAG queries: 12
- Policy version: `1.0.0`

The Pilot Golden Dataset has undergone human semantic review.

## Running the baseline

From the project root:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_audit.py
.\.venv\Scripts\python.exe scripts\evaluate_rag.py
```

Use `--output artifacts/evals/<run-id>` on both commands to place all four
JSON/Markdown reports in one run directory. JSON is the machine-readable source
of truth; Markdown is generated deterministically from the persisted JSON.

The Audit baseline reports violation precision/recall/F1, four-state accuracy,
confusion matrices, final-decision accuracy, exact match, automation coverage,
determinate accuracy, appropriate abstention, and per-rule metrics. The RAG
baseline reports Recall@1, Recall@3, set-based Recall@3, MRR, negative no-result
accuracy, and query-level details. No quality threshold is enforced.

## Files

- `contracts/audit_case.schema.json`: contract for one deterministic audit case.
- `contracts/rag_query.schema.json`: contract for one policy-retrieval query.
- `data/audit_pilot.jsonl`: 12 synthetic audit cases.
- `data/rag_pilot.jsonl`: 12 synthetic retrieval queries.
- `metrics.py`: dependency-free metric functions.
- `runner.py`: approved-label adapters, evaluation orchestration, and reports.

Each non-empty JSONL line is one independent record encoded as UTF-8 JSON.
The schemas use JSON Schema Draft 2020-12 and reject unknown fields.

## Label lifecycle

Every pilot record has `label.status = APPROVED` and non-empty `reviewer`,
`reviewed_at`, and `review_notes` metadata. The existing
`label.candidate_expected` field name is retained for schema compatibility; its
contents are the approved Pilot Golden labels. A future schema version may
rename this field without changing the approved label content.

## Scope of contract tests

`tests/test_eval_contracts.py` checks file shape, IDs, policy pinning, label
lifecycle, referential integrity, and planned pilot coverage. It deliberately
does not execute `app.audit_engine` or `app.rag`, keeping contract validation
independent of current business implementation output.

All audit records are synthetic and use fictional names and merchants.
