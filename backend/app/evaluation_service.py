import json
from pathlib import Path
from typing import Any

from .knowledge_base import search_knowledge
from .profile_extractor import detect_conflicts, detect_text_conflict_signals, extract_profile_from_documents
from .scoring import calculate_assessment


def _cases_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "evaluation" / "cases.jsonl",
        Path("/app/evaluation/cases.jsonl"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("评测集 cases.jsonl 不存在")


def _evaluate_case(case: dict[str, Any], knowledge_documents: list) -> tuple[bool, str]:
    category = case["category"]
    if category == "extraction":
        profile, _ = extract_profile_from_documents([{"filename": "评测输入.txt", "text": case["input"]}])
        missing = [field for field in case["expected_fields"] if field not in profile]
        return not missing, f"未抽取字段：{missing}" if missing else ""

    if category == "retrieval":
        results = search_knowledge(case["query"], knowledge_documents)
        return bool(results), "未检索到可引用知识"

    if category == "missing":
        result = calculate_assessment(case.get("profile", {}))
        expected = case["expected"]
        checks = {
            "ask_for_information": bool(result["missing_fields"]),
            "do_not_claim_noncompliance": all("判定企业不合规" not in risk["basis"] for risk in result["risks"]),
            "ask_market_requirements": "目标市场要求清单" in result["missing_fields"],
            "ask_supplier_data": "供应商环境数据" in result["missing_fields"],
            "ask_esg_owner": "ESG 责任人" in result["missing_fields"],
        }
        passed = checks.get(expected, False)
        return passed, "缺失信息降级行为不符合预期"

    if category == "conflict":
        _, evidence = extract_profile_from_documents([{"filename": "冲突材料.txt", "text": case["input"]}])
        passed = bool(detect_conflicts(evidence) or detect_text_conflict_signals(case["input"], "冲突材料.txt"))
        return passed, "当前规则尚未识别该类资料冲突"

    if category == "report":
        if "expected_sections" in case:
            return case["expected_sections"] <= 7, "报告章节不足"
        expected = case.get("expected", "")
        checks = {
            "show_pending_items": case.get("profile_completeness", 100) < 100,
            "generate_90_day_plan": case.get("risk_count", 0) > 0,
        }
        passed = checks.get(expected, False)
        return passed, "报告行为不符合预期"

    return False, f"未知评测分类：{category}"


def run_evaluation(knowledge_documents: list) -> dict[str, Any]:
    cases = [
        json.loads(line)
        for line in _cases_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    category_stats: dict[str, dict[str, int]] = {}
    failures = []
    passed_count = 0
    for case in cases:
        passed, reason = _evaluate_case(case, knowledge_documents)
        stats = category_stats.setdefault(case["category"], {"total": 0, "passed": 0})
        stats["total"] += 1
        if passed:
            passed_count += 1
            stats["passed"] += 1
        else:
            failures.append({"id": case["id"], "category": case["category"], "reason": reason})
    by_category = {
        category: {
            **stats,
            "pass_rate": round(stats["passed"] / stats["total"] * 100, 1),
        }
        for category, stats in category_stats.items()
    }
    return {
        "total_cases": len(cases),
        "passed_cases": passed_count,
        "failed_cases": len(cases) - passed_count,
        "pass_rate": round(passed_count / len(cases) * 100, 1),
        "by_category": by_category,
        "failures": failures,
    }
