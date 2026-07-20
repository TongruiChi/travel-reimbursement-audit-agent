# Architecture

## Purpose

The system is a backend MVP for enterprise travel reimbursement audit. It demonstrates how structured business data, Markdown policy rules, keyword-based RAG, deterministic checks, and an Agent orchestration layer can work together in a small but explainable application.

## Layered Architecture

```text
API layer
  FastAPI routes in app/main.py

Application layer
  app/agent.py
  app/audit_engine.py
  app/reporting.py
  app/rag.py

Data access layer
  app/crud.py
  app/database.py

Domain models
  app/models.py
  app/schemas.py

Storage and data files
  data/reimbursement.db
  data/mock/mock_trip_expenses.json
  data/rules/company_travel_policy.md
```

## Data Flow

```text
Mock trip and expense data
  -> SQLite tables: trips, expenses, receipts
  -> Agent loads trip and expenses
  -> Agent builds rule retrieval queries
  -> RAG retrieves relevant Markdown policy rules
  -> deterministic audit engine evaluates expenses
  -> audit report dict is generated
  -> audit_reports table stores summary and detail_json
  -> reporting module formats report JSON for APIs
```

## Agent Execution Flow

The Agent is a deterministic orchestration layer:

```text
LOAD_TRIP
  -> LOAD_EXPENSES
  -> RETRIEVE_RULES
  -> RUN_DETERMINISTIC_AUDIT
  -> SAVE_AUDIT_REPORT
  -> RETURN_FINAL_DECISION
```

Each step is recorded in the response. This makes the flow easy to explain in interviews and easy to debug during development.

## Where RAG Fits

RAG is used for policy context retrieval:

- Read company rules from `data/rules/company_travel_policy.md`.
- Split Markdown by rule IDs such as `R-HOTEL-001`.
- Match keyword queries against rule title and content.
- Return rule evidence to the Agent.

RAG does not decide whether an expense is approved or rejected. Final audit decisions are made by deterministic logic in `app/audit_engine.py`.

## Why Deterministic Audit Rules Matter

Reimbursement compliance needs reproducible outputs:

- Date range checks must always behave the same way.
- Amount limits must be exact.
- Missing receipt flags must be explicit.
- High-severity issues must consistently affect the final status.

The MVP therefore keeps the audit engine deterministic and explainable.

## Why The MVP Does Not Use A Real LLM

The current MVP avoids real LLM calls for three reasons:

- Interview demo stability: no network, API key, or model variability.
- Compliance reliability: core audit decisions must be deterministic.
- Architecture clarity: the Agent boundary is shown without hiding logic inside prompts.

In a production version, an LLM can be added as a planner or explanation generator, while the deterministic audit engine remains the source of truth.

## Future LLM Agent Upgrade

A future version could introduce:

- LLM planner for deciding which tools to call.
- Embedding retrieval for richer policy search.
- OCR extraction for invoice images.
- Human review summaries generated from structured flags.
- Tool-call tracing and evaluation.

The recommended production direction is:

```text
LLM planner
  -> RAG policy retrieval tool
  -> deterministic audit tool
  -> report persistence tool
  -> human-readable explanation generator
```

The deterministic audit tool should remain authoritative for compliance status.
