import os
import sys
from datetime import datetime

import httpx


BASE_URL = os.getenv("GREEN_ADVISOR_URL", "http://127.0.0.1:8010")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(response: httpx.Response, expected: int = 200) -> dict:
    if response.status_code != expected:
        raise RuntimeError(f"{response.request.method} {response.request.url} -> {response.status_code}: {response.text}")
    return response.json()


def create_project(client: httpx.Client, suffix: str, company: str, profile: dict | None = None) -> int:
    result = check(
        client.post(
            "/api/projects",
            json={
                "name": f"{suffix}-{datetime.now():%H%M%S}",
                "company_name": company,
                "industry": "储能设备制造",
                "region": "浙江",
                "target_market": "英国",
                "goal": "端到端验收",
                "profile": profile or {},
            },
        ),
        201,
    )
    return result["id"]


def upload(client: httpx.Client, project_id: int, filename: str) -> None:
    path = os.path.join(ROOT, "demo", filename)
    with open(path, "rb") as handle:
        check(client.post(f"/api/projects/{project_id}/documents", files={"file": (filename, handle, "text/plain")}), 201)


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=30, trust_env=False) as client:
        health = check(client.get("/api/health/ready"))
        assert health["database"] == "ok"

        complete_id = create_project(client, "完整资料案例", "华东储能科技有限公司")
        upload(client, complete_id, "01-complete-company.txt")
        complete_extraction = check(client.post(f"/api/projects/{complete_id}/extract"))
        assert len(complete_extraction["extracted_profile"]) >= 12
        complete_assessment = check(client.post(f"/api/projects/{complete_id}/assess"))
        check(
            client.post(
                f"/api/projects/{complete_id}/reviews",
                json={"decision": "approved", "comment": "自动化冒烟测试通过", "reviewer": "Smoke Test"},
            ),
            201,
        )
        pdf = client.get(f"/api/projects/{complete_id}/report.pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

        missing_id = create_project(client, "资料缺失案例", "启明新能源设备有限公司")
        upload(client, missing_id, "02-missing-information.txt")
        check(client.post(f"/api/projects/{missing_id}/extract"))
        missing_assessment = check(client.post(f"/api/projects/{missing_id}/assess"))
        assert len(missing_assessment["missing_fields"]) >= 8

        conflict_id = create_project(client, "资料冲突案例", "远航工业科技有限公司")
        upload(client, conflict_id, "03-conflict-a.txt")
        upload(client, conflict_id, "03-conflict-b.txt")
        conflict_extraction = check(client.post(f"/api/projects/{conflict_id}/extract"))
        assert any(item["field"] == "carbon_inventory" for item in conflict_extraction["conflicts"])
        assert "carbon_inventory" not in conflict_extraction["merged_profile"]
        conflict = next(item for item in check(client.get(f"/api/projects/{conflict_id}/conflicts")) if item["field"] == "carbon_inventory")
        check(
            client.post(
                f"/api/projects/{conflict_id}/conflicts/{conflict['id']}/resolve",
                json={"selected_value": True, "reviewer": "Smoke Test", "comment": "核验报告A后采纳肯定事实"},
            )
        )
        resolved_project = check(client.get(f"/api/projects/{conflict_id}"))
        assert resolved_project["profile"]["carbon_inventory"] is True

        evaluation = check(client.post("/api/evaluations/run"))
        metrics = check(client.get("/api/metrics/summary"))
        print(
            f"PASS complete_score={complete_assessment['total_score']} "
            f"missing_fields={len(missing_assessment['missing_fields'])} "
            f"conflicts={len(conflict_extraction['conflicts'])} resolved=1 "
            f"evaluation={evaluation['passed_cases']}/{evaluation['total_cases']} "
            f"workflow_runs={metrics['total_runs']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise
