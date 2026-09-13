# Interview Talking Points

## 30-Second Introduction

This is a FastAPI backend MVP for enterprise travel reimbursement audit. It stores trip, expense, and receipt data in SQLite, retrieves relevant company reimbursement policy rules from Markdown through keyword-based RAG, runs deterministic compliance checks, orchestrates the workflow with a hand-written Agent, persists JSON audit reports, and exposes report query APIs for review.

## 2-Minute Architecture Introduction

The system has four main layers:

1. API layer: FastAPI endpoints and Swagger documentation.
2. Data layer: SQLite, SQLAlchemy ORM, CRUD functions.
3. Policy and audit layer: Markdown rules, keyword RAG, deterministic audit engine.
4. Agent and reporting layer: hand-written Agent orchestration, audit report persistence, JSON report query APIs.

The request flow is:

```text
Trip and expense data
  -> RAG retrieves policy context
  -> Agent coordinates tools
  -> audit engine produces deterministic status and flags
  -> audit report is saved
  -> report APIs expose reviewable JSON
```

## Project Highlights

- End-to-end backend MVP, not only isolated functions.
- Clear separation between RAG, Agent, audit engine, and reporting.
- Deterministic compliance results for interview demo stability.
- JSON audit reports that can be reviewed after generation.
- Mock data includes realistic abnormal cases.

## Agent Design Highlights

The Agent is an orchestration layer:

```text
load trip
load expenses
retrieve rules
run deterministic audit
save report
return final decision
```

Important point:

```text
Agent coordinates tools; audit rules remain in the audit engine.
```

This makes it easy to replace the current deterministic planner with a real LLM planner later without changing the audit engine.

## RAG Design Highlights

Current RAG behavior:

- Read Markdown policy document.
- Split by rule IDs such as `R-GEN-001`.
- Search title and content by simple keywords.
- Return relevant rules to the Agent as policy evidence.

RAG does not decide the final audit result. It helps explain which policy rules are relevant.

## Rule Engine Design Highlights

The deterministic audit engine checks:

- Trip date range.
- Positive amount.
- Receipt existence.
- Hotel amount limit.
- Meal amount limit.
- Traffic amount limit.
- Other expense manual review.

This design keeps compliance results stable and reproducible.

## Why Not A Real LLM Now

The MVP intentionally avoids real LLM calls because:

- The interview demo should run without API keys or network dependencies.
- Compliance decisions should be deterministic.
- Amount limits and missing receipt checks should not vary by prompt.
- The architecture can still show an Agent pattern without hiding logic in a model.

## What Production Would Need

- Authentication and authorization.
- Multi-tenant enterprise configuration.
- Real receipt upload and OCR.
- Rule management UI.
- Human review workflow.
- Audit trail and permissions.
- Broader integration coverage, deployment checks, and CI release gates.
- Monitoring and structured logging.
- Frontend dashboard.
- Export to Excel or PDF.

## Common Follow-Up Questions

### Is this a real Agent?

It is a deterministic MVP Agent. It orchestrates tools and records execution steps. It does not use an LLM planner yet, but the design leaves a clear upgrade path.

### Why keep the audit engine separate from the Agent?

Because compliance checks must be testable, reproducible, and independent from planning logic. The Agent decides the workflow; the audit engine decides compliance.

### What is the role of RAG?

RAG retrieves relevant company policy context. It supports explanation and traceability, but the final decision comes from deterministic code.

### How would you add an LLM later?

Use the LLM as a planner or explanation generator. It could choose tools, summarize flags, and draft reviewer notes. The deterministic audit engine should remain authoritative.

### How would you improve retrieval?

Move from keyword matching to embeddings and a vector database, add metadata filters for category and rule severity, and evaluate retrieval quality with test cases.

### How would you handle real receipts?

Add file upload, storage, OCR extraction, receipt field validation, and matching between extracted receipt data and expense records.

### What is the current MVP boundary?

It is backend-only, uses mock data, Markdown rules, keyword retrieval, deterministic checks, and JSON reports. It does not include OCR, real LLMs, frontend UI, or production authentication.
