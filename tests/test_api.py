LEGACY_FLAG_KEYS = {"rule_id", "flag", "severity", "message"}


def _assert_legacy_item_flags(items):
    assert all(isinstance(item["flags"], list) for item in items)
    flags = [flag for item in items for flag in item["flags"]]
    assert flags
    assert all(isinstance(flag, dict) for flag in flags)
    assert all(set(flag) == LEGACY_FLAG_KEYS for flag in flags)
    assert all(
        all(isinstance(flag[key], str) for key in LEGACY_FLAG_KEYS)
        for flag in flags
    )


def test_core_api_flow_uses_test_database(seeded_db, client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    rules = client.get("/rules/search", params={"query": "住宿 超标", "top_k": 3})
    assert rules.status_code == 200
    rule_ids = [item["rule"]["rule_id"] for item in rules.json()["results"]]
    assert "R-HOTEL-001" in rule_ids

    audit = client.post(f"/audit/trips/{seeded_db}")
    assert audit.status_code == 201
    audit_json = audit.json()
    assert audit_json["status"] == "REJECTED"
    assert len(audit_json["detail"]["items"]) == 6
    _assert_legacy_item_flags(audit_json["detail"]["items"])
    assert all("rule_results" in item for item in audit_json["detail"]["items"])

    agent = client.post(f"/agent/audit/trips/{seeded_db}")
    assert agent.status_code == 201
    agent_json = agent.json()
    assert agent_json["final_decision"]["status"] == "REJECTED"
    assert len(agent_json["audit_report"]["detail"]["items"]) == 6
    _assert_legacy_item_flags(agent_json["audit_report"]["detail"]["items"])
    assert all(
        "rule_results" in item
        for item in agent_json["audit_report"]["detail"]["items"]
    )

    report_id = agent_json["audit_report"]["report_id"]
    report = client.get(f"/audit/reports/{report_id}")
    assert report.status_code == 200
    assert report.json()["status"] == "REJECTED"

    latest = client.get(f"/trips/{seeded_db}/audit-reports/latest")
    assert latest.status_code == 200
    assert latest.json()["status"] == "REJECTED"
    assert len(latest.json()["detail"]["items"]) == 6


def test_api_returns_404_for_missing_trip(client):
    response = client.post("/agent/audit/trips/999999")

    assert response.status_code == 404
