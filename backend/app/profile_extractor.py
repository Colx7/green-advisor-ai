import re
import json
from typing import Any


FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "annual_energy_data": ("能源台账", "能耗台账", "年度能源", "电力和天然气", "能源数据"),
    "carbon_inventory": ("温室气体盘查", "碳盘查", "范围一", "范围二", "scope 1", "scope 2"),
    "reduction_target": ("减排目标", "降碳目标", "碳目标", "排放下降", "碳中和目标"),
    "green_certifications": ("iso 14001", "绿色工厂", "环境认证", "绿色认证", "产品碳足迹认证"),
    "lifecycle_assessment": ("生命周期评价", "生命周期评估", "lca"),
    "eco_design": ("生态设计", "绿色设计", "可拆解设计", "可回收设计"),
    "supplier_code": ("供应商行为准则", "供应商环境准则", "供应商管理规范"),
    "supplier_data": ("供应商环境数据", "供应商碳数据", "供应商排放数据", "向供应商收集"),
    "supplier_audit": ("供应商审核", "供应商审计", "供应商现场检查"),
    "esg_owner": (
        "esg负责人",
        "esg 负责人",
        "可持续发展负责人",
        "可持续发展工作由",
        "绿色发展负责人",
    ),
    "esg_policy": ("esg制度", "esg 制度", "环境管理制度", "可持续发展制度"),
    "sustainability_report": ("可持续发展报告", "esg报告", "esg 报告", "环境信息披露"),
    "target_market_requirements": ("目标市场要求清单", "海外法规清单", "合规要求清单", "市场准入清单"),
    "compliance_owner": ("合规负责人", "海外合规负责人", "法规负责人"),
    "evidence_archive": ("证据归档", "合规档案", "文件留存", "证明材料归档"),
}


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？!?\n\r]+", text) if item.strip()]


NEGATIVE_TERMS = ("尚未", "暂未", "未开展", "未完成", "未建立", "没有", "无相关", "未指定", "未进行")


def _is_negative(sentence: str) -> bool:
    return any(term in sentence for term in NEGATIVE_TERMS)


def extract_profile_from_documents(documents: list[dict[str, Any]]) -> tuple[dict, list[dict]]:
    profile: dict[str, Any] = {}
    evidence: list[dict] = []
    certification_values: list[str] = []

    for document in documents:
        filename = document["filename"]
        for sentence in _sentences(document.get("text", "")):
            normalized = sentence.lower().replace("：", ":")
            for field, patterns in FIELD_PATTERNS.items():
                matched = next((pattern for pattern in patterns if pattern in normalized), None)
                if field == "supplier_data" and "供应商" in normalized and "收集" in normalized and "数据" in normalized:
                    matched = matched or "供应商数据收集句式"
                if field == "supplier_audit" and "供应商" in normalized and any(
                    term in normalized for term in ("审核", "审计", "检查")
                ):
                    matched = matched or "供应商审核句式"
                if not matched:
                    continue
                negative = _is_negative(sentence)
                if negative:
                    profile[field] = False
                elif field == "green_certifications":
                    value = "ISO 14001" if "iso 14001" in normalized else sentence[:80]
                    if value not in certification_values:
                        certification_values.append(value)
                    profile[field] = certification_values
                elif field in {"esg_owner", "compliance_owner"}:
                    owner_match = re.search(r"([\u4e00-\u9fff]{2,4}(?:经理|总监|主任|负责人))", sentence)
                    profile[field] = owner_match.group(1) if owner_match else sentence[:80]
                else:
                    profile[field] = True
                evidence.append(
                    {
                        "field": field,
                        "value": profile[field],
                        "filename": filename,
                        "excerpt": sentence[:240],
                        "confidence": 0.85,
                        "method": "keyword-rule-v1",
                    }
                )
    return profile, evidence


def detect_conflicts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        grouped.setdefault(item["field"], []).append(item)
    conflicts = []
    for field, items in grouped.items():
        values = {json.dumps(item["value"], ensure_ascii=False, sort_keys=True) for item in items}
        if len(values) <= 1:
            continue
        conflicts.append(
            {
                "field": field,
                "values": [item["value"] for item in items],
                "evidence": [
                    {"filename": item["filename"], "excerpt": item["excerpt"], "value": item["value"]}
                    for item in items
                ],
            }
        )
    return conflicts


def detect_text_conflict_signals(text: str, filename: str = "材料") -> list[dict[str, Any]]:
    signal_patterns = (
        r"已(?:完成|建立|开展).{0,30}(?:尚未|暂未|未完成|未开展|未启动)",
        r"(?:尚未|暂未|未完成|未开展|未启动).{0,30}已(?:完成|建立|开展)",
        r"(?:冲突|矛盾)",
        r"分别.{0,30}(?:和|与)",
        r"相差\s*\d+(?:\.\d+)?%",
    )
    if not any(re.search(pattern, text) for pattern in signal_patterns):
        return []
    return [
        {
            "field": "general_data_conflict",
            "values": ["材料存在显式矛盾"],
            "evidence": [{"filename": filename, "excerpt": text[:240], "value": "需人工确认"}],
        }
    ]
