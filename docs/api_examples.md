# API Examples

Base URL:

```text
http://127.0.0.1:8765
```

Start the server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## GET /health

Purpose: check whether the API is running.

Request:

```text
GET /health
```

Expected core result:

```json
{
  "status": "ok"
}
```

## GET /rules/search

Purpose: retrieve relevant reimbursement policy rules from Markdown.

Request:

```text
GET /rules/search?query=住宿%20超标&top_k=3
```

Expected core fields:

```text
query
count
results[].score
results[].rule.rule_id
results[].rule.title
```

Expected relevant rule:

```text
R-HOTEL-001
```

## POST /audit/trips/{trip_id}

Purpose: run the deterministic audit engine for a trip and save an audit report.

Request:

```text
POST /audit/trips/1
```

Expected core fields:

```text
report_id
trip_id
status
total_amount
summary
detail
```

Expected result with mock data:

```text
status = REJECTED
total_amount = 1663.5
detail.items count = 6
```

## POST /agent/audit/trips/{trip_id}

Purpose: run the hand-written Agent orchestration flow.

Request:

```text
POST /agent/audit/trips/1
```

Expected core fields:

```text
agent_name
trip_id
steps
retrieved_rules
audit_report
final_decision
```

Expected result with mock data:

```text
agent_name = TravelReimbursementAuditAgent
final_decision.status = REJECTED
steps count = 6
retrieved_rules count = 6
audit_report.detail.items count = 6
```

## GET /audit/reports/{report_id}

Purpose: retrieve one complete audit report by ID.

Request:

```text
GET /audit/reports/1
```

Expected core fields:

```text
report_id
trip_id
status
total_amount
summary
detail
created_at
```

Expected result:

```text
report_id = 1
status = REJECTED
detail.items count = 6
```

If the report does not exist:

```json
{
  "detail": "Audit report not found"
}
```

## GET /trips/{trip_id}/audit-reports

Purpose: list audit report summaries for one trip.

Request:

```text
GET /trips/1/audit-reports
```

Expected core fields:

```text
trip_id
count
reports[]
```

Expected result:

```text
trip_id = 1
count >= 1
reports[0].status = REJECTED
```

If the trip does not exist:

```json
{
  "detail": "Trip not found"
}
```

## GET /trips/{trip_id}/audit-reports/latest

Purpose: retrieve the latest complete report for one trip.

Request:

```text
GET /trips/1/audit-reports/latest
```

Expected result:

```text
trip_id = 1
status = REJECTED
detail.items count = 6
```

If the trip exists but has no reports:

```json
{
  "detail": "No audit report found for this trip"
}
```
