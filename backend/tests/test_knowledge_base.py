from types import SimpleNamespace

from app.knowledge_base import search_knowledge


def test_search_returns_no_result_for_unrelated_query():
    document = SimpleNamespace(
        id=1,
        title="绿色供应链指南",
        authority="测试机构",
        topic="绿色制造与供应链",
        region="中国",
        source_url="https://example.com",
        content="供应商环境管理和绿色制造要求。",
    )
    assert search_knowledge("员工食堂菜单", [document]) == []


def test_search_ranks_matching_topic():
    carbon = SimpleNamespace(
        id=1,
        title="温室气体盘查",
        authority="A",
        topic="温室气体盘查",
        region="全球",
        source_url="https://example.com/a",
        content="企业应收集范围一和范围二排放数据。",
    )
    supply = SimpleNamespace(
        id=2,
        title="供应链管理",
        authority="B",
        topic="绿色制造与供应链",
        region="中国",
        source_url="https://example.com/b",
        content="企业应管理供应商环境数据。",
    )
    results = search_knowledge("碳排放盘查和范围一数据", [supply, carbon])
    assert results[0]["id"] == 1
