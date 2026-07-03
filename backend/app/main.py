from pathlib import Path
import shutil
from time import perf_counter
from urllib.parse import quote
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import delete, func, select, text as sql_text
from sqlalchemy.orm import Session, selectinload

from .config import get_settings
from .ai_client import DifyClient
from .database import Base, SessionLocal, engine, get_db
from .document_parser import SUPPORTED_EXTENSIONS, extract_text
from .evaluation_service import run_evaluation
from .knowledge_base import SEED_KNOWLEDGE, attach_citations, search_knowledge, seed_knowledge
from .models import Assessment, DataConflict, Document, KnowledgeDocument, ProfileEvidence, Project, Review, WorkflowRun
from .profile_extractor import detect_conflicts, detect_text_conflict_signals, extract_profile_from_documents
from .pdf_report import build_pdf_report
from .runtime_state import runtime_state
from .schemas import (
    AssessmentOut,
    ConflictResolve,
    DataConflictOut,
    DocumentOut,
    EvidenceOut,
    EvaluationSummary,
    ExtractionOut,
    KnowledgeCreate,
    KnowledgeOut,
    KnowledgeSearchResult,
    MetricsSummary,
    ProfileUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ReviewCreate,
    ReviewOut,
    TaskStatusOut,
    WorkflowRunOut,
)
from .scoring import calculate_assessment

settings = get_settings()
dify_client = DifyClient()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)
with SessionLocal() as startup_db:
    seed_knowledge(startup_db)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_utf8_json_charset(request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json") and "charset=" not in content_type.lower():
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


def get_project_or_404(db: Session, project_id: int, detailed: bool = False) -> Project:
    query = select(Project).where(Project.id == project_id)
    if detailed:
        query = query.options(selectinload(Project.assessment), selectinload(Project.reviews))
    project = db.scalar(query)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "llm_mode": settings.llm_mode}


@app.get("/api/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict:
    database_ok = False
    try:
        db.execute(sql_text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False
    redis_ok = runtime_state.available()
    return {
        "status": "ready" if database_ok else "not_ready",
        "database": "ok" if database_ok else "unavailable",
        "redis": "ok" if redis_ok else "degraded",
        "redis_required": False,
    }


@app.post("/api/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    profile = data.pop("profile")
    profile.setdefault("industry", payload.industry)
    profile.setdefault("region", payload.region)
    profile.setdefault("target_market", payload.target_market)
    project = Project(**data, profile=profile)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@app.get("/api/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id, detailed=True)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    for model in (DataConflict, ProfileEvidence, Document, WorkflowRun, Review, Assessment):
        db.execute(delete(model).where(model.project_id == project_id))
    db.delete(project)
    db.commit()
    runtime_state.delete_project_status(project_id)
    project_dir = Path(settings.upload_dir) / str(project_id)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)
    return Response(status_code=204)


@app.put("/api/projects/{project_id}/profile", response_model=ProjectOut)
def update_profile(project_id: int, payload: ProfileUpdate, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    project.profile = payload.profile
    project.status = "profile_ready"
    db.commit()
    db.refresh(project)
    return project


@app.post("/api/projects/{project_id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    original_name = Path(file.filename or "unnamed").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"仅支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    project_dir = Path(settings.upload_dir) / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / f"{uuid4().hex}{suffix}"
    content = file.file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="单个文件不能超过 10MB")
    target.write_bytes(content)
    try:
        text = extract_text(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"文件解析失败：{exc}") from exc
    document = Document(
        project_id=project.id,
        filename=original_name,
        content_type=file.content_type or "application/octet-stream",
        storage_path=str(target),
        extracted_text=text[:100_000],
    )
    db.add(document)
    project.status = "documents_ready"
    db.commit()
    db.refresh(document)
    return document


@app.get("/api/projects/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return list(
        db.scalars(select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc()))
    )


@app.post("/api/projects/{project_id}/extract", response_model=ExtractionOut)
def extract_project_profile(project_id: int, db: Session = Depends(get_db)):
    started_at = perf_counter()
    project = get_project_or_404(db, project_id)
    documents = list(db.scalars(select(Document).where(Document.project_id == project_id)))
    if not documents:
        raise HTTPException(status_code=409, detail="请先上传企业资料")
    local_profile, local_evidence = extract_profile_from_documents(
        [{"filename": document.filename, "text": document.extracted_text} for document in documents]
    )
    extracted = local_profile
    evidence_data = local_evidence
    extraction_mode = "local"
    warnings: list[str] = []
    fallback_used = False
    run_error = ""
    conflicts = detect_conflicts(local_evidence)
    for document in documents:
        conflicts.extend(detect_text_conflict_signals(document.extracted_text, document.filename))
    if settings.llm_mode == "dify":
        if dify_client.enabled:
            try:
                combined_text = "\n\n".join(
                    f"文件：{document.filename}\n{document.extracted_text}" for document in documents
                )[:100_000]
                extracted, evidence_data = dify_client.extract_profile(combined_text, str(project_id))
                conflicts = detect_conflicts(evidence_data)
                extraction_mode = "dify"
            except Exception as exc:
                fallback_used = True
                run_error = str(exc)[:500]
                warnings.append(f"Dify 调用失败，已降级为本地抽取：{run_error}")
        else:
            fallback_used = True
            run_error = "Dify 模式已启用，但API地址或密钥未配置"
            warnings.append(f"{run_error}，已降级为本地抽取")
    conflict_fields = {item["field"] for item in conflicts}
    extracted = {key: value for key, value in extracted.items() if key not in conflict_fields}
    merged = dict(project.profile or {})
    for field in conflict_fields:
        merged.pop(field, None)
    merged.update(extracted)
    project.profile = merged
    project.status = "profile_ready"
    for old in db.scalars(select(ProfileEvidence).where(ProfileEvidence.project_id == project_id)):
        db.delete(old)
    for old in db.scalars(select(DataConflict).where(DataConflict.project_id == project_id)):
        db.delete(old)
    evidence_models = [ProfileEvidence(project_id=project_id, **item) for item in evidence_data]
    conflict_models = [DataConflict(project_id=project_id, **item) for item in conflicts]
    db.add_all(evidence_models)
    db.add_all(conflict_models)
    workflow_run = WorkflowRun(
            project_id=project_id,
            operation="profile_extraction",
            provider=extraction_mode,
            status="degraded" if fallback_used else "success",
            latency_ms=round((perf_counter() - started_at) * 1000),
            fallback_used=fallback_used,
            error=run_error,
            details={
                "document_count": len(documents),
                "field_count": len(extracted),
                "conflict_count": len(conflicts),
            },
        )
    db.add(workflow_run)
    db.commit()
    db.refresh(workflow_run)
    runtime_state.set_project_status(
        project_id,
        {
            "project_id": project_id,
            "operation": workflow_run.operation,
            "provider": workflow_run.provider,
            "status": workflow_run.status,
            "latency_ms": workflow_run.latency_ms,
            "fallback_used": workflow_run.fallback_used,
            "created_at": workflow_run.created_at.isoformat(),
        },
    )
    return {
        "extracted_profile": extracted,
        "merged_profile": merged,
        "evidence": evidence_models,
        "document_count": len(documents),
        "extraction_mode": extraction_mode,
        "warnings": warnings,
        "conflicts": conflicts,
    }


@app.get("/api/projects/{project_id}/evidence", response_model=list[EvidenceOut])
def list_profile_evidence(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return list(
        db.scalars(
            select(ProfileEvidence)
            .where(ProfileEvidence.project_id == project_id)
            .order_by(ProfileEvidence.field, ProfileEvidence.id)
        )
    )


@app.get("/api/projects/{project_id}/conflicts", response_model=list[DataConflictOut])
def list_data_conflicts(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return list(
        db.scalars(
            select(DataConflict)
            .where(DataConflict.project_id == project_id)
            .order_by(DataConflict.created_at.desc())
        )
    )


@app.post(
    "/api/projects/{project_id}/conflicts/{conflict_id}/resolve",
    response_model=DataConflictOut,
)
def resolve_data_conflict(
    project_id: int,
    conflict_id: int,
    payload: ConflictResolve,
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    conflict = db.scalar(
        select(DataConflict).where(
            DataConflict.id == conflict_id,
            DataConflict.project_id == project_id,
        )
    )
    if conflict is None:
        raise HTTPException(status_code=404, detail="冲突记录不存在")
    if conflict.status != "open":
        raise HTTPException(status_code=409, detail="该冲突已经解决")
    allowed_values = [item.get("value") for item in conflict.evidence]
    if payload.selected_value not in allowed_values:
        raise HTTPException(status_code=422, detail="选中值必须来自冲突证据")
    if conflict.field == "general_data_conflict":
        raise HTTPException(status_code=422, detail="通用资料冲突需先人工修正企业画像")

    profile = dict(project.profile or {})
    profile[conflict.field] = payload.selected_value
    project.profile = profile
    project.status = "profile_ready"
    conflict.status = "resolved"
    workflow_run = WorkflowRun(
        project_id=project_id,
        operation="conflict_resolution",
        provider="human",
        status="success",
        latency_ms=0,
        details={
            "conflict_id": conflict_id,
            "field": conflict.field,
            "selected_value": payload.selected_value,
            "reviewer": payload.reviewer,
            "comment": payload.comment,
        },
    )
    db.add(workflow_run)
    db.commit()
    db.refresh(conflict)
    db.refresh(workflow_run)
    runtime_state.set_project_status(
        project_id,
        {
            "project_id": project_id,
            "operation": workflow_run.operation,
            "provider": workflow_run.provider,
            "status": workflow_run.status,
            "latency_ms": workflow_run.latency_ms,
            "fallback_used": workflow_run.fallback_used,
            "created_at": workflow_run.created_at.isoformat(),
        },
    )
    assess_project(project_id, db)
    return conflict


@app.post("/api/projects/{project_id}/assess", response_model=AssessmentOut)
def assess_project(project_id: int, db: Session = Depends(get_db)):
    started_at = perf_counter()
    project = get_project_or_404(db, project_id, detailed=True)
    result = calculate_assessment(project.profile or {})
    knowledge_documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.active.is_(True))))
    result["risks"] = attach_citations(result["risks"], knowledge_documents)
    if project.assessment is None:
        project.assessment = Assessment(project_id=project.id, **result)
    else:
        for key, value in result.items():
            setattr(project.assessment, key, value)
    project.status = "pending_review"
    workflow_run = WorkflowRun(
            project_id=project_id,
            operation="assessment",
            provider="local-rules+rAG",
            status="success",
            latency_ms=round((perf_counter() - started_at) * 1000),
            details={"risk_count": len(result["risks"]), "score": result["total_score"]},
        )
    db.add(workflow_run)
    db.commit()
    db.refresh(project.assessment)
    db.refresh(workflow_run)
    runtime_state.set_project_status(
        project_id,
        {
            "project_id": project_id,
            "operation": workflow_run.operation,
            "provider": workflow_run.provider,
            "status": workflow_run.status,
            "latency_ms": workflow_run.latency_ms,
            "fallback_used": workflow_run.fallback_used,
            "created_at": workflow_run.created_at.isoformat(),
        },
    )
    return result


@app.get("/api/knowledge", response_model=list[KnowledgeOut])
def list_knowledge(db: Session = Depends(get_db)):
    protected_titles = {item["title"] for item in SEED_KNOWLEDGE}
    documents = list(db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id)))
    return [
        KnowledgeOut.model_validate(document).model_copy(update={"protected": document.title in protected_titles})
        for document in documents
    ]


@app.post("/api/knowledge", response_model=KnowledgeOut, status_code=201)
def create_knowledge(payload: KnowledgeCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == payload.title))
    if existing:
        raise HTTPException(status_code=409, detail="同名知识文档已存在")
    document = KnowledgeDocument(**payload.model_dump())
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@app.get("/api/knowledge/search", response_model=list[KnowledgeSearchResult])
def search_knowledge_api(q: str, limit: int = 3, db: Session = Depends(get_db)):
    if not q.strip():
        raise HTTPException(status_code=422, detail="检索内容不能为空")
    documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.active.is_(True))))
    return search_knowledge(q, documents, max(1, min(limit, 10)))


@app.delete("/api/knowledge/{knowledge_id}", status_code=204)
def delete_knowledge(knowledge_id: int, db: Session = Depends(get_db)):
    document = db.get(KnowledgeDocument, knowledge_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    protected_titles = {item["title"] for item in SEED_KNOWLEDGE}
    if document.title in protected_titles:
        raise HTTPException(status_code=409, detail="官方种子来源受保护，不能删除")
    db.delete(document)
    db.commit()
    return Response(status_code=204)


@app.get("/api/workflow-runs", response_model=list[WorkflowRunOut])
def list_workflow_runs(limit: int = 50, db: Session = Depends(get_db)):
    return list(
        db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(max(1, min(limit, 200))))
    )


@app.get("/api/projects/{project_id}/task-status", response_model=TaskStatusOut)
def get_project_task_status(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    cached = runtime_state.get_project_status(project_id)
    if cached:
        return {**cached, "source": "redis"}
    latest = db.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(1)
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="该项目暂无任务运行记录")
    return {
        "project_id": project_id,
        "operation": latest.operation,
        "provider": latest.provider,
        "status": latest.status,
        "latency_ms": latest.latency_ms,
        "fallback_used": latest.fallback_used,
        "source": "mysql",
        "created_at": latest.created_at.isoformat(),
    }


@app.get("/api/metrics/summary", response_model=MetricsSummary)
def metrics_summary(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(WorkflowRun)) or 0
    success = db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status == "success")) or 0
    degraded = db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status == "degraded")) or 0
    failed = db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.status == "failed")) or 0
    average_latency = db.scalar(select(func.avg(WorkflowRun.latency_ms))) or 0
    return {
        "total_runs": total,
        "successful_runs": success,
        "degraded_runs": degraded,
        "failed_runs": failed,
        "success_rate": round(success / total * 100, 1) if total else 100.0,
        "average_latency_ms": round(float(average_latency), 1),
        "current_mode": settings.llm_mode,
        "dify_configured": dify_client.enabled,
        "redis_available": runtime_state.available(),
    }


@app.post("/api/evaluations/run", response_model=EvaluationSummary)
def run_evaluation_api(db: Session = Depends(get_db)):
    documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.active.is_(True))))
    return run_evaluation(documents)


@app.post("/api/projects/{project_id}/reviews", response_model=ReviewOut, status_code=201)
def review_project(project_id: int, payload: ReviewCreate, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if project.status not in {"pending_review", "needs_revision", "completed"}:
        raise HTTPException(status_code=409, detail="项目尚未生成诊断结果")
    review = Review(project_id=project.id, **payload.model_dump())
    project.status = {
        "approved": "completed",
        "rejected": "needs_revision",
        "needs_revision": "needs_revision",
    }[payload.decision]
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@app.get("/api/projects/{project_id}/report")
def get_report(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id, detailed=True)
    if project.assessment is None:
        raise HTTPException(status_code=409, detail="请先执行诊断")
    assessment = project.assessment
    return {
        "title": f"{project.company_name}绿色转型与出海准备度诊断报告",
        "disclaimer": "本报告为 AI 辅助分析演示，不构成法律、审计或认证意见，需由专业顾问复核。",
        "project": ProjectOut.model_validate(project),
        "assessment": AssessmentOut.model_validate(assessment, from_attributes=True),
        "review_status": project.status,
    }


@app.get("/api/projects/{project_id}/report.pdf")
def download_pdf_report(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id, detailed=True)
    if project.assessment is None:
        raise HTTPException(status_code=409, detail="请先执行诊断")
    content = build_pdf_report(project, project.assessment)
    filename = quote(f"{project.company_name}-绿色诊断报告.pdf")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
