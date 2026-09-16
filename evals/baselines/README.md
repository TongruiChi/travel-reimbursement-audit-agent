# Versioned Evaluation Baselines

Runtime evaluation reports are generated under `artifacts/evals/<run-id>/`.
They contain detailed JSON facts and Markdown projections, are ignored by Git,
and can be regenerated with the evaluation CLIs.

Reviewed baseline summaries live in this directory and are version controlled.
They preserve compact, decision-relevant metrics and provenance without copying
all runtime query and mismatch details.

`pilot-v1.json` is the first Pilot baseline:

- 12 approved Audit cases.
- 12 approved RAG queries.
- Policy version `1.0.0`.
- Source run `20260916T061255Z` from a dirty worktree.

This Pilot baseline is an evaluation checkpoint, not a production-quality
conclusion. A later Phase 1 dataset expansion must create a new versioned
baseline file rather than overwrite historical baselines.
