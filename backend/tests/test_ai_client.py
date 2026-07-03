import pytest

from app.ai_client import DifyClient


def test_dify_extract_profile_requires_evidence(monkeypatch):
    client = DifyClient()
    monkeypatch.setattr(
        client,
        "run_workflow",
        lambda inputs, user: {"data": {"outputs": {"profile": {"carbon_inventory": True}}}},
    )
    with pytest.raises(ValueError, match="可追溯证据"):
        client.extract_profile("完成碳盘查", "test-user")


def test_dify_extract_profile_accepts_json_outputs(monkeypatch):
    client = DifyClient()
    monkeypatch.setattr(
        client,
        "run_workflow",
        lambda inputs, user: {
            "data": {
                "outputs": {
                    "profile": '{"carbon_inventory": true, "unsupported": true}',
                    "evidence": (
                        '[{"field":"carbon_inventory","value":true,"filename":"报告.txt",'
                        '"excerpt":"已完成范围一和范围二盘查","confidence":0.91}]'
                    ),
                }
            }
        },
    )
    profile, evidence = client.extract_profile("完成碳盘查", "test-user")
    assert profile == {"carbon_inventory": True}
    assert evidence[0]["method"] == "dify-workflow"
    assert evidence[0]["confidence"] == 0.91
