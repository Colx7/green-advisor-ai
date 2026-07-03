from app.profile_extractor import detect_conflicts, detect_text_conflict_signals, extract_profile_from_documents


def test_extractor_returns_source_evidence():
    profile, evidence = extract_profile_from_documents(
        [{"filename": "能源报告.txt", "text": "企业已建立能源台账。减排目标为2030年下降30%。"}]
    )
    assert profile == {"annual_energy_data": True, "reduction_target": True}
    assert {item["field"] for item in evidence} == {"annual_energy_data", "reduction_target"}
    assert all(item["filename"] == "能源报告.txt" for item in evidence)


def test_extractor_does_not_infer_absent_fields():
    profile, evidence = extract_profile_from_documents(
        [{"filename": "简介.txt", "text": "本公司位于浙江，主要生产储能设备。"}]
    )
    assert profile == {}
    assert evidence == []


def test_extractor_detects_positive_negative_conflict():
    profile, evidence = extract_profile_from_documents(
        [
            {"filename": "报告A.txt", "text": "企业已完成温室气体盘查。"},
            {"filename": "报告B.txt", "text": "企业尚未开展温室气体盘查。"},
        ]
    )
    assert profile["carbon_inventory"] is False
    conflicts = detect_conflicts(evidence)
    assert conflicts[0]["field"] == "carbon_inventory"
    assert {item["value"] for item in conflicts[0]["evidence"]} == {True, False}


def test_explicit_conflict_signal_requires_review():
    conflicts = detect_text_conflict_signals("两份报告的年度能源数据相差50%", "核验记录.txt")
    assert conflicts[0]["field"] == "general_data_conflict"
    assert conflicts[0]["evidence"][0]["filename"] == "核验记录.txt"
