# Demo Script

## Before The Demo

Open a terminal at the repository root. The commands below use Windows PowerShell.

Use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe --version
```

## 1. Reset Mock Data

```powershell
.\.venv\Scripts\python.exe scripts\seed_mock_data.py --reset
```

Expected:

```text
Existing MVP data cleared successfully.
Mock data seeded successfully with trip_id: 1
```

## 2. Run The Command-Line Walkthrough

```powershell
.\.venv\Scripts\python.exe scripts\demo_walkthrough_check.py
```

Expected highlights:

```text
[OK] Rule chunks loaded: 10
[OK] Expenses loaded: 6
[OK] Agent status: REJECTED
[OK] Audit items: 6
Demo walkthrough check passed.
```

## 3. Start FastAPI

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Open Swagger:

```text
http://127.0.0.1:8765/docs
```

## 4. Recommended Swagger Demo Order

1. `GET /health`
2. `GET /rules/search?query=住宿%20超标`
3. `POST /audit/trips/1`
4. `POST /agent/audit/trips/1`
5. `GET /audit/reports/1`
6. `GET /trips/1/audit-reports`
7. `GET /trips/1/audit-reports/latest`

## 5. What To Explain While Demoing

Start with the business problem:

```text
Enterprise reimbursement audit needs to collect expenses, retrieve policy rules,
run stable compliance checks, flag abnormal items, and produce a reviewable JSON report.
```

Explain the key architecture:

```text
RAG retrieves policy context. The Agent orchestrates tools. The deterministic audit engine makes the final compliance decision.
```

Explain why the mock data returns `REJECTED`:

- One hotel expense exceeds 800 CNY.
- One meal expense exceeds 150 CNY.
- One traffic expense is outside the trip date range.
- One "other" expense has no receipt and requires review.

## 6. Expected Result

The main Agent audit endpoint should return:

```text
agent_name = TravelReimbursementAuditAgent
final_decision.status = REJECTED
steps = 6
retrieved_rules = 6
audit_report.detail.items = 6
```

## 7. Common Interview Questions

### Why use an Agent here?

The Agent coordinates multiple tools: load data, retrieve rules, run audit, save report, return final decision. It is not the rule engine itself.

### Why not use a real LLM in the MVP?

Compliance decisions must be deterministic. A real LLM can be added later for planning and explanation, but the source of truth should remain the deterministic audit engine.

### What does RAG do?

RAG retrieves relevant policy rules from Markdown and gives the Agent explainable evidence. It does not directly approve or reject expenses.

### What would be needed for production?

Production-grade authentication, permissions, OCR, configurable rules, human review workflow, audit logs, broader integration coverage, CI release gates, monitoring, and a frontend dashboard.
