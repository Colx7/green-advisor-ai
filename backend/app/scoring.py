from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Check:
    field: str
    label: str
    points: float


DIMENSIONS = {
    "energy_carbon": (
        "能源与碳数据",
        25.0,
        [
            Check("annual_energy_data", "年度能源数据", 9),
            Check("carbon_inventory", "温室气体盘查", 9),
            Check("reduction_target", "量化减排目标", 7),
        ],
    ),
    "green_product": (
        "产品绿色属性",
        20.0,
        [
            Check("green_certifications", "绿色或环境认证", 8),
            Check("lifecycle_assessment", "产品生命周期评价", 7),
            Check("eco_design", "生态设计机制", 5),
        ],
    ),
    "supply_chain": (
        "供应链管理",
        20.0,
        [
            Check("supplier_code", "供应商环境准则", 7),
            Check("supplier_data", "供应商环境数据", 7),
            Check("supplier_audit", "供应商审核机制", 6),
        ],
    ),
    "governance": (
        "治理与披露",
        20.0,
        [
            Check("esg_owner", "ESG 责任人", 7),
            Check("esg_policy", "ESG 或环境制度", 7),
            Check("sustainability_report", "可持续发展披露", 6),
        ],
    ),
    "overseas": (
        "海外合规准备",
        15.0,
        [
            Check("target_market_requirements", "目标市场要求清单", 6),
            Check("compliance_owner", "海外合规责任人", 5),
            Check("evidence_archive", "合规证据归档", 4),
        ],
    ),
}


def _is_present(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return value is not None


def calculate_assessment(profile: dict[str, Any]) -> dict[str, Any]:
    dimensions = []
    all_checks = [check for _, _, checks in DIMENSIONS.values() for check in checks]
    present_count = sum(_is_present(profile.get(check.field)) for check in all_checks)
    missing_fields: list[str] = []

    for key, (name, max_score, checks) in DIMENSIONS.items():
        score = 0.0
        evidence: list[str] = []
        pending: list[str] = []
        for check in checks:
            value = profile.get(check.field)
            if _is_present(value):
                score += check.points
                summary = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                evidence.append(f"{check.label}：{summary}")
            else:
                pending.append(check.label)
                missing_fields.append(check.label)
        dimensions.append(
            {
                "key": key,
                "name": name,
                "score": score,
                "max_score": max_score,
                "evidence": evidence,
                "pending": pending,
            }
        )

    total_score = sum(item["score"] for item in dimensions)
    completeness = round(present_count / len(all_checks) * 100, 1)
    risks = build_risks(profile, dimensions)
    actions = build_action_plan(risks, missing_fields)
    return {
        "total_score": round(total_score, 1),
        "completeness": completeness,
        "dimensions": dimensions,
        "risks": risks,
        "action_plan": actions,
        "missing_fields": missing_fields,
        "rule_version": "1.0.0",
    }


def build_risks(profile: dict[str, Any], dimensions: list[dict]) -> list[dict]:
    risks: list[dict] = []
    market = profile.get("target_market") or "目标海外市场"
    if not _is_present(profile.get("target_market_requirements")):
        risks.append(
            {
                "title": f"{market}绿色合规要求尚未形成清单",
                "level": "高",
                "basis": "企业资料中未发现目标市场绿色要求清单；资料缺失不等同于不合规。",
                "recommendation": "由合规负责人确认适用要求、产品范围、生效时间和证明材料。",
                "requires_review": True,
            }
        )
    if not _is_present(profile.get("carbon_inventory")):
        risks.append(
            {
                "title": "碳排放基础数据不足",
                "level": "高",
                "basis": "未提供温室气体盘查结果，暂时无法验证排放边界与基准年。",
                "recommendation": "明确组织和运营边界，收集能源活动数据并开展基础盘查。",
                "requires_review": True,
            }
        )
    if not _is_present(profile.get("supplier_data")):
        risks.append(
            {
                "title": "供应链环境数据可追溯性不足",
                "level": "中",
                "basis": "资料中未发现供应商环境或碳数据收集记录。",
                "recommendation": "先覆盖关键供应商，建立数据模板、提交频率和证据留存规则。",
                "requires_review": True,
            }
        )
    if not _is_present(profile.get("esg_owner")):
        risks.append(
            {
                "title": "绿色治理责任尚不明确",
                "level": "中",
                "basis": "企业画像中未识别到 ESG 或绿色合规责任人。",
                "recommendation": "指定业务负责人并明确跨部门数据收集和审核职责。",
                "requires_review": False,
            }
        )
    if not risks:
        risks.append(
            {
                "title": "基础准备较完整，需进行专业复核",
                "level": "低",
                "basis": "当前结构化字段较完整，但本系统不替代专业合规判断。",
                "recommendation": "由专业顾问核验原始证据并针对具体产品确认适用要求。",
                "requires_review": True,
            }
        )
    return risks


def build_action_plan(risks: list[dict], missing_fields: list[str]) -> list[dict]:
    items = [
        {
            "phase": "1-30 天",
            "task": "确认项目负责人并补齐关键企业数据",
            "owner": "项目经理 / ESG 负责人",
            "deliverable": "责任矩阵与资料缺口清单",
            "priority": "高",
        },
        {
            "phase": "31-60 天",
            "task": "完成目标市场要求映射与差距分析",
            "owner": "合规负责人 / 外部顾问",
            "deliverable": "适用要求和证据矩阵",
            "priority": "高",
        },
        {
            "phase": "61-90 天",
            "task": "复核整改证据并形成管理层报告",
            "owner": "项目经理 / 管理层",
            "deliverable": "整改跟踪表与审核版报告",
            "priority": "中",
        },
    ]
    if missing_fields:
        items[0]["task"] += f"（当前待确认 {len(missing_fields)} 项）"
    return items

