# Enterprise Travel Reimbursement Audit Agent

## 1. Project Overview

This project is a FastAPI backend MVP for enterprise travel reimbursement collection and audit.
It lets a user store trip, expense, and receipt data, retrieve relevant company reimbursement rules from Markdown, run a deterministic compliance audit, orchestrate the flow with a hand-written Agent, persist audit reports, and query JSON report details for review.

The project is designed for interview demonstration. It shows how RAG, deterministic business rules, and an Agent orchestration layer can work together without depending on a real LLM in the MVP.

## 2. Why This Project

Travel reimbursement audit is a good Agent use case because it combines:

- Structured business data: trips, expenses, receipts.
- Enterprise policy context: reimbursement rules stored in Markdown.
- Deterministic compliance checks: date range, amount limits, receipt requirements.
- Explainable audit output: flags, rule hits, item status, final decision.

The MVP keeps compliance decisions deterministic because reimbursement checks must be stable, reproducible, and auditable.

## 3. Key Features

- FastAPI backend with Swagger documentation.
- SQLite persistence through SQLAlchemy.
- Pydantic request and response schemas.
- Mock trip, expense, and receipt data.
- Markdown company travel policy.
- Keyword-based RAG rule retrieval.
- Deterministic audit engine.
- Hand-written Agent orchestration layer.
- JSON audit report persistence in `audit_reports`.
- Report query endpoints for detail, history, and latest report.
- Automated pytest coverage for the API, RAG, audit engine, Agent, and reporting.
- GitHub Actions CI on Python 3.11 and 3.12.

## 4. Tech Stack

- Python
- FastAPI
- SQLite
- SQLAlchemy
- Pydantic
- Pydantic Settings
- Uvicorn
- Pytest
- GitHub Actions
- Markdown policy files
- Standard-library demo scripts

No LLM, LangChain, vector database, OCR, or frontend is included in the current MVP.

## 5. System Architecture

```text
Trip / Expense / Receipt data
  -> SQLite
  -> Markdown company policy
  -> keyword RAG rule retrieval
  -> hand-written Agent orchestration
  -> deterministic audit engine
  -> audit flags and audit status
  -> audit_reports table
  -> JSON report query APIs
```

Main modules:

- `app/main.py`: FastAPI routes.
- `app/models.py`: SQLAlchemy ORM models.
- `app/schemas.py`: Pydantic schemas.
- `app/crud.py`: database operations.
- `app/rag.py`: keyword-based Markdown rule retrieval.
- `app/audit_engine.py`: deterministic compliance audit logic.
- `app/agent.py`: Agent orchestration layer.
- `app/reporting.py`: JSON report formatting.
- `scripts/seed_mock_data.py`: reset and import mock data.
- `scripts/demo_walkthrough_check.py`: command-line main-flow check.

## 6. Agent Workflow

The Agent is an orchestration layer, not a pile of audit rules.

```text
1. LOAD_TRIP
2. LOAD_EXPENSES
3. RETRIEVE_RULES
4. RUN_DETERMINISTIC_AUDIT
5. SAVE_AUDIT_REPORT
6. RETURN_FINAL_DECISION
```

The Agent coordinates tools. Audit rules remain in `app/audit_engine.py`.

## 7. RAG Rule Retrieval

The RAG layer reads `data/rules/company_travel_policy.md`, splits rules by IDs such as `R-HOTEL-001`, and performs simple keyword matching over rule titles and content.

RAG is used as policy context retrieval. It provides explainable rule evidence for the Agent, but it does not make the final compliance decision.

Example:

```text
GET /rules/search?query=住宿%20超标
```

Expected relevant rule:

```text
R-HOTEL-001
```

## 8. Deterministic Audit Engine

The audit engine checks:

- Expense date is within trip date range.
- Expense amount is greater than zero.
- Receipt exists.
- Hotel expense does not exceed 800 CNY.
- Meal expense does not exceed 150 CNY.
- Traffic or local traffic expense does not exceed 300 CNY.
- Other expense requires manual review.

Final report status:

- `APPROVED`: no flags.
- `NEEDS_REVIEW`: flags exist, but no high-severity issue.
- `REJECTED`: high-severity issue exists.

## 9. Database Models

Current SQLite tables:

- `trips`
- `expenses`
- `receipts`
- `audit_reports`

`audit_reports.detail_json` stores the structured audit report as JSON text for later review.

## 10. Quick Start

### Windows PowerShell

Create a virtual environment and install development dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Reset mock data:

```powershell
.\.venv\Scripts\python.exe scripts\seed_mock_data.py --reset
```

Run the main-flow check:

```powershell
.\.venv\Scripts\python.exe scripts\demo_walkthrough_check.py
```

Start the API server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

### Linux

Create a virtual environment and install development dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Reset mock data and run the main-flow check:

```bash
.venv/bin/python scripts/seed_mock_data.py --reset
.venv/bin/python scripts/demo_walkthrough_check.py
```

Start the API server:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Open Swagger:

```text
http://127.0.0.1:8765/docs
```

## 11. Automated Testing and CI

Run the automated test suite locally:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux:

```bash
.venv/bin/python -m pytest -q
```

The validated v0.1.0 baseline is `14 passed`. GitHub Actions runs the project on Python 3.11 and 3.12 and performs the compile check, pytest suite, mock data reset, and demo walkthrough.

## 12. Demo Walkthrough

Recommended demo order:

1. Reset mock data.
2. Run `scripts/demo_walkthrough_check.py`.
3. Start FastAPI.
4. Open Swagger.
5. Check `GET /health`.
6. Search rules with `GET /rules/search?query=住宿%20超标`.
7. Generate a deterministic audit report with `POST /audit/trips/1`.
8. Generate an Agent audit result with `POST /agent/audit/trips/1`.
9. Query report detail with `GET /audit/reports/1`.
10. Query report history with `GET /trips/1/audit-reports`.
11. Query the latest report with `GET /trips/1/audit-reports/latest`.

## 13. Core API Endpoints

- `GET /health`
- `POST /trips/`
- `GET /trips/{trip_id}`
- `POST /expenses/`
- `GET /trips/{trip_id}/expenses`
- `POST /receipts/`
- `GET /rules/search`
- `POST /audit/trips/{trip_id}`
- `POST /agent/audit/trips/{trip_id}`
- `GET /audit/reports/{report_id}`
- `GET /trips/{trip_id}/audit-reports`
- `GET /trips/{trip_id}/audit-reports/latest`

## 14. Example Audit Result

With the bundled mock data, trip `1` returns:

```text
status = REJECTED
total_amount = 1663.5
expense_count = 6
audit_items = 6
```

Expected flags include:

- `HOTEL_AMOUNT_EXCEED_LIMIT`
- `MEAL_AMOUNT_EXCEED_LIMIT`
- `EXPENSE_OUT_OF_TRIP_DATE`
- `RECEIPT_MISSING`
- `OTHER_EXPENSE_NEED_REVIEW`

## 15. Current MVP Scope

Implemented:

- Backend-only FastAPI MVP.
- Mock expense and receipt data.
- Markdown policy rules.
- Keyword RAG retrieval.
- Deterministic audit engine.
- Hand-written Agent orchestration.
- JSON report persistence and query APIs.
- Automated pytest suite.
- GitHub Actions CI on Python 3.11 and 3.12.

Not implemented:

- Real OCR invoice recognition.
- Real LLM planner or reasoning model.
- Embedding retrieval or vector database.
- Enterprise authentication and authorization.
- Multi-tenant rule management.
- Frontend dashboard.
- Approval workflow.
- Export to Excel/PDF.

## 16. Future Improvements

- Replace keyword retrieval with embeddings and a vector database.
- Add an LLM planner while keeping deterministic audit checks as tools.
- Add OCR for invoice and receipt extraction.
- Build an admin UI for reimbursement rule configuration.
- Add approval workflow and manual review assignment.
- Add role-based access control.
- Add report export.
