import json
from pathlib import Path


def main() -> None:
    path = Path(__file__).with_name("cases.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [case["id"] for case in cases]
    assert len(cases) >= 30, "评测集至少需要 30 条"
    assert len(ids) == len(set(ids)), "评测用例 ID 不能重复"
    categories = {case["category"] for case in cases}
    assert categories == {"extraction", "retrieval", "missing", "conflict", "report"}
    print(f"评测集校验通过：{len(cases)} 条，{len(categories)} 类")


if __name__ == "__main__":
    main()

