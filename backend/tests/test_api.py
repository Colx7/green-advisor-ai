from io import BytesIO

from pypdf import PdfReader


def project_payload():
    return {
        "name": "英国市场绿色准备度诊断",
        "company_name": "华东储能科技有限公司",
        "industry": "储能设备制造",
        "region": "浙江",
        "target_market": "英国",
        "goal": "识别主要绿色合规准备缺口",
        "profile": {"annual_energy_data": True, "esg_owner": "王经理"},
    }


def test_project_assessment_review_flow(client):
    client.post(
        "/api/knowledge",
        json={
            "title": "测试碳盘查来源",
            "authority": "测试机构",
            "topic": "温室气体盘查",
            "region": "全球",
            "source_url": "https://example.com/complete/very-long-source-address",
            "published_at": "2026-01-01",
            "content": "企业碳排放盘查应收集范围一和范围二活动数据，并形成能够复核的温室气体排放清单。",
        },
    )
    created = client.post("/api/projects", json=project_payload())
    assert created.status_code == 201
    project_id = created.json()["id"]

    assessment = client.post(f"/api/projects/{project_id}/assess")
    assert assessment.status_code == 200
    assert assessment.json()["total_score"] > 0

    review = client.post(
        f"/api/projects/{project_id}/reviews",
        json={"decision": "approved", "comment": "演示审核通过", "reviewer": "顾问 A"},
    )
    assert review.status_code == 201

    report = client.get(f"/api/projects/{project_id}/report")
    assert report.status_code == 200
    assert report.json()["review_status"] == "completed"

    pdf = client.get(f"/api/projects/{project_id}/report.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf.content))
    links = []
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            action = annotation.get("/A")
            if action and action.get("/URI"):
                links.append(action.get("/URI"))
    assert "https://example.com/complete/very-long-source-address" in links


def test_unknown_project_returns_404(client):
    assert client.get("/api/projects/999").status_code == 404


def test_json_response_declares_utf8(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"


def test_delete_project_removes_related_data(client, monkeypatch):
    monkeypatch.setattr("app.main.runtime_state.delete_project_status", lambda project_id: True)
    project_id = client.post("/api/projects", json=project_payload()).json()["id"]
    client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("资料.txt", "企业已建立年度能源台账".encode("utf-8"), "text/plain")},
    )
    client.post(f"/api/projects/{project_id}/extract")
    client.post(f"/api/projects/{project_id}/assess")
    client.post(
        f"/api/projects/{project_id}/reviews",
        json={"decision": "approved", "comment": "删除测试", "reviewer": "测试顾问"},
    )
    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.get(f"/api/projects/{project_id}/documents").status_code == 404


def test_upload_text_document(client):
    project_id = client.post("/api/projects", json=project_payload()).json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("企业资料.txt", "年度能源数据：已建立台账".encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201
    assert "年度能源数据" in response.json()["extracted_text"]


def test_reject_unsupported_document(client):
    project_id = client.post("/api/projects", json=project_payload()).json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("malware.exe", b"not executable", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_upload_extract_and_reassess(client):
    payload = project_payload()
    payload["profile"] = {}
    project_id = client.post("/api/projects", json=payload).json()["id"]
    material = (
        "公司已建立年度能源台账。2025年完成范围一和范围二温室气体盘查。"
        "公司获得ISO 14001认证。可持续发展工作由王经理负责。"
        "供应商行为准则包含环境保护要求。"
    )
    uploaded = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("企业绿色资料.txt", material.encode("utf-8"), "text/plain")},
    )
    assert uploaded.status_code == 201

    extraction = client.post(f"/api/projects/{project_id}/extract")
    assert extraction.status_code == 200
    extracted = extraction.json()["extracted_profile"]
    assert extracted["annual_energy_data"] is True
    assert extracted["carbon_inventory"] is True
    assert extracted["green_certifications"] == ["ISO 14001"]
    assert len(extraction.json()["evidence"]) >= 5

    assessment = client.post(f"/api/projects/{project_id}/assess")
    assert assessment.status_code == 200
    assert assessment.json()["total_score"] == 40


def test_extract_requires_document(client):
    project_id = client.post("/api/projects", json=project_payload()).json()["id"]
    assert client.post(f"/api/projects/{project_id}/extract").status_code == 409


def test_knowledge_search_and_risk_citation(client):
    knowledge = {
        "title": "企业温室气体盘查演示指南",
        "authority": "测试标准机构",
        "topic": "温室气体盘查",
        "region": "全球",
        "source_url": "https://example.com/ghg",
        "published_at": "2026-01-01",
        "content": "企业温室气体盘查应明确组织边界，收集范围一和范围二活动数据，并保存可复核的证据资料。",
    }
    created = client.post("/api/knowledge", json=knowledge)
    assert created.status_code == 201

    searched = client.get("/api/knowledge/search", params={"q": "碳排放盘查基础数据"})
    assert searched.status_code == 200
    assert searched.json()[0]["title"] == knowledge["title"]

    project_id = client.post("/api/projects", json=project_payload()).json()["id"]
    assessment = client.post(f"/api/projects/{project_id}/assess")
    carbon_risk = next(item for item in assessment.json()["risks"] if "碳排放" in item["title"])
    assert carbon_risk["evidence_status"] == "supported"
    assert carbon_risk["citations"][0]["authority"] == "测试标准机构"
    knowledge_id = created.json()["id"]
    assert client.delete(f"/api/knowledge/{knowledge_id}").status_code == 204
    assert client.get("/api/knowledge/search", params={"q": "碳排放盘查基础数据"}).json() == []


def test_official_seed_title_is_protected(client):
    response = client.post(
        "/api/knowledge",
        json={
            "title": "绿色工厂梯度培育及管理暂行办法",
            "authority": "中华人民共和国工业和信息化部",
            "topic": "绿色制造与供应链",
            "region": "中国",
            "source_url": "https://example.com/protected",
            "published_at": "2024-01-19",
            "content": "用于验证官方种子来源保护状态，内容长度满足知识条目的最小校验要求。",
        },
    )
    assert response.status_code == 201
    knowledge_id = response.json()["id"]
    listed = client.get("/api/knowledge").json()
    assert listed[0]["protected"] is True
    deleted = client.delete(f"/api/knowledge/{knowledge_id}")
    assert deleted.status_code == 409


def test_workflow_metrics_are_recorded(client, monkeypatch):
    monkeypatch.setattr("app.main.runtime_state.set_project_status", lambda project_id, payload: False)
    monkeypatch.setattr("app.main.runtime_state.get_project_status", lambda project_id: None)
    monkeypatch.setattr("app.main.runtime_state.available", lambda: False)
    project_id = client.post("/api/projects", json=project_payload()).json()["id"]
    client.post(f"/api/projects/{project_id}/assess")
    metrics = client.get("/api/metrics/summary")
    assert metrics.status_code == 200
    assert metrics.json()["total_runs"] == 1
    assert metrics.json()["successful_runs"] == 1
    assert metrics.json()["success_rate"] == 100.0
    runs = client.get("/api/workflow-runs").json()
    assert runs[0]["operation"] == "assessment"
    assert runs[0]["details"]["risk_count"] >= 1
    task_status = client.get(f"/api/projects/{project_id}/task-status")
    assert task_status.status_code == 200
    assert task_status.json()["source"] == "mysql"
    assert metrics.json()["redis_available"] is False


def test_readiness_reports_database(client, monkeypatch):
    monkeypatch.setattr("app.main.runtime_state.available", lambda: True)
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
        "redis": "ok",
        "redis_required": False,
    }


def test_conflicting_documents_are_excluded_from_profile(client):
    payload = project_payload()
    payload["profile"] = {}
    project_id = client.post("/api/projects", json=payload).json()["id"]
    for filename, text in [
        ("报告A.txt", "企业已完成温室气体盘查。"),
        ("报告B.txt", "企业尚未开展温室气体盘查。"),
    ]:
        response = client.post(
            f"/api/projects/{project_id}/documents",
            files={"file": (filename, text.encode("utf-8"), "text/plain")},
        )
        assert response.status_code == 201
    extraction = client.post(f"/api/projects/{project_id}/extract")
    assert extraction.status_code == 200
    assert "carbon_inventory" not in extraction.json()["merged_profile"]
    assert extraction.json()["conflicts"][0]["field"] == "carbon_inventory"
    conflicts = client.get(f"/api/projects/{project_id}/conflicts")
    assert conflicts.status_code == 200
    assert conflicts.json()[0]["status"] == "open"
    conflict_id = conflicts.json()[0]["id"]
    resolved = client.post(
        f"/api/projects/{project_id}/conflicts/{conflict_id}/resolve",
        json={"selected_value": True, "reviewer": "测试顾问", "comment": "核验原始盘查报告后采纳"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    project = client.get(f"/api/projects/{project_id}").json()
    assert project["profile"]["carbon_inventory"] is True
    assert project["assessment"]["total_score"] >= 9
    repeated = client.post(
        f"/api/projects/{project_id}/conflicts/{conflict_id}/resolve",
        json={"selected_value": False, "reviewer": "测试顾问"},
    )
    assert repeated.status_code == 409
    runs = client.get("/api/workflow-runs").json()
    assert any(item["operation"] == "conflict_resolution" for item in runs)


def test_evaluation_endpoint_runs_all_cases(client):
    response = client.post("/api/evaluations/run")
    assert response.status_code == 200
    result = response.json()
    assert result["total_cases"] == 30
    assert result["passed_cases"] + result["failed_cases"] == 30
    assert set(result["by_category"]) == {"extraction", "retrieval", "missing", "conflict", "report"}
