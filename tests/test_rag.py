from app.rag import rule_rag


def test_rule_chunks_loaded():
    rule_ids = [chunk.rule_id for chunk in rule_rag.rule_chunks]

    assert len(rule_ids) == 10
    assert "R-GEN-001" in rule_ids
    assert "R-GEN-002" in rule_ids
    assert "R-HOTEL-001" in rule_ids
    assert "R-MEAL-001" in rule_ids
    assert "R-OTHER-001" in rule_ids


def test_keyword_search_returns_expected_rules():
    hotel_ids = [item["rule"]["rule_id"] for item in rule_rag.search("住宿 超标", 3)]
    meal_ids = [item["rule"]["rule_id"] for item in rule_rag.search("餐饮 金额", 3)]
    receipt_ids = [item["rule"]["rule_id"] for item in rule_rag.search("凭证 缺失", 3)]
    exact_ids = [item["rule"]["rule_id"] for item in rule_rag.search("R-HOTEL-001", 3)]

    assert "R-HOTEL-001" in hotel_ids
    assert "R-MEAL-001" in meal_ids
    assert "R-GEN-002" in receipt_ids
    assert exact_ids == ["R-HOTEL-001"]


def test_keyword_search_with_no_results_returns_empty_list():
    assert rule_rag.search("zzzz_nonexistent_keyword_12345", 3) == []
