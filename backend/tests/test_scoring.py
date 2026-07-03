from app.scoring import calculate_assessment


def test_empty_profile_is_pending_not_noncompliant():
    result = calculate_assessment({})
    assert result["total_score"] == 0
    assert result["completeness"] == 0
    assert len(result["missing_fields"]) == 15
    assert any("资料缺失不等同于不合规" in risk["basis"] for risk in result["risks"])


def test_full_profile_scores_100():
    fields = {
        "annual_energy_data": True,
        "carbon_inventory": True,
        "reduction_target": True,
        "green_certifications": ["ISO 14001"],
        "lifecycle_assessment": True,
        "eco_design": True,
        "supplier_code": True,
        "supplier_data": True,
        "supplier_audit": True,
        "esg_owner": "张经理",
        "esg_policy": True,
        "sustainability_report": True,
        "target_market_requirements": True,
        "compliance_owner": "李经理",
        "evidence_archive": True,
    }
    result = calculate_assessment(fields)
    assert result["total_score"] == 100
    assert result["completeness"] == 100
    assert result["missing_fields"] == []
