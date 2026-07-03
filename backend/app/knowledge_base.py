import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import KnowledgeDocument


SEED_KNOWLEDGE = [
    {
        "title": "绿色工厂梯度培育及管理暂行办法",
        "authority": "中华人民共和国工业和信息化部",
        "topic": "绿色制造与供应链",
        "region": "中国",
        "published_at": "2024-01-19",
        "source_url": "https://www.miit.gov.cn/threestrategy/zcgh/zcfg/art/2024/art_94a3c71e903b49b79923e4df397c31ab.html",
        "content": "绿色工厂梯度培育以绿色工厂为基础，并由绿色工业园区、绿色供应链管理企业提供支撑。企业应关注绿色制造、绿色供应链、环境信息披露、动态管理以及评价资料的真实性和可追溯性。",
    },
    {
        "title": "IFRS S1 可持续相关财务信息披露一般要求",
        "authority": "IFRS Foundation / ISSB",
        "topic": "ESG治理与披露",
        "region": "全球",
        "published_at": "2023-06",
        "source_url": "https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s1-general-requirements/",
        "content": "IFRS S1要求披露可能影响企业前景的可持续相关风险和机会，包括治理、战略、风险识别与管理流程，以及指标、目标和目标完成进展。",
    },
    {
        "title": "GHG Protocol Corporate Standard",
        "authority": "Greenhouse Gas Protocol",
        "topic": "温室气体盘查",
        "region": "全球",
        "published_at": "",
        "source_url": "https://ghgprotocol.org/corporate-standard",
        "content": "企业温室气体盘查应明确组织边界和运营边界，识别排放源，收集活动数据并形成可复核的排放清单。范围一和范围二是企业盘查的重要基础。",
    },
    {
        "title": "UK Carbon Border Adjustment Mechanism Policy Summary",
        "authority": "HM Revenue & Customs",
        "topic": "英国出海合规",
        "region": "英国",
        "published_at": "2026-04-09",
        "source_url": "https://www.gov.uk/government/publications/carbon-border-adjustment-mechanism-cbam-policy-summary/carbon-border-adjustment-mechanism-cbam-policy-summary",
        "content": "英国CBAM计划自2027年1月1日起实施，当前公布范围覆盖铝、水泥、化肥、氢、钢铁等指定商品。企业需结合具体商品编码确认是否适用，不能仅因进入英国市场就判定受其约束。",
    },
]


TOPIC_TERMS = {
    "英国出海合规": ("英国", "海外", "市场", "合规", "cbam", "商品编码"),
    "温室气体盘查": ("碳", "排放", "盘查", "范围一", "范围二", "能源"),
    "绿色制造与供应链": (
        "供应链",
        "供应商",
        "绿色制造",
        "绿色工厂",
        "环境",
        "生命周期",
        "生态设计",
        "产品",
    ),
    "ESG治理与披露": ("治理", "责任", "负责人", "披露", "esg", "制度"),
}


def seed_knowledge(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(KnowledgeDocument)):
        return
    db.add_all([KnowledgeDocument(**item) for item in SEED_KNOWLEDGE])
    db.commit()


def _query_terms(query: str) -> set[str]:
    lowered = query.lower()
    terms = set(re.findall(r"[a-z0-9]+", lowered))
    for topic_terms in TOPIC_TERMS.values():
        terms.update(term for term in topic_terms if term in lowered)
    return terms


def search_knowledge(query: str, documents: list[KnowledgeDocument], limit: int = 3) -> list[dict[str, Any]]:
    query_terms = _query_terms(query)
    results = []
    for document in documents:
        haystack = f"{document.title} {document.topic} {document.region} {document.content}".lower()
        topic_terms = TOPIC_TERMS.get(document.topic, ())
        matched = {term for term in query_terms if term in haystack}
        topic_hits = sum(1 for term in topic_terms if term in query.lower())
        score = len(matched) + topic_hits * 1.5
        if score <= 0:
            continue
        results.append(
            {
                "id": document.id,
                "title": document.title,
                "authority": document.authority,
                "topic": document.topic,
                "region": document.region,
                "source_url": document.source_url,
                "excerpt": document.content[:260],
                "score": round(score, 2),
            }
        )
    return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]


def attach_citations(risks: list[dict], documents: list[KnowledgeDocument]) -> list[dict]:
    enriched = []
    for risk in risks:
        item = dict(risk)
        citations = search_knowledge(f"{risk['title']} {risk['basis']} {risk['recommendation']}", documents, limit=2)
        item["citations"] = citations
        item["evidence_status"] = "supported" if citations else "insufficient"
        if not citations:
            item["requires_review"] = True
        enriched.append(item)
    return enriched
