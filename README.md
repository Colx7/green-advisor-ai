# 绿智顾问

企业绿色转型与出海合规 AI 工作台。项目面向企业客户和咨询顾问，将企业资料转化为可解释的绿色成熟度评分、资料缺口、优先风险和 90 天行动计划，并通过人工审核形成报告。

> 本项目是 AI 辅助咨询演示，不构成法律、审计、认证或投资意见。

## 已实现

- 企业诊断项目创建与列表
- 项目搜索、状态筛选和关联数据安全删除
- TXT、Markdown、PDF、DOCX、XLSX 文件上传和文本解析
- 企业画像 JSON 数据管理
- 上传资料后的本地字段抽取、证据原文与置信度
- 抽取结果自动合并画像并重新诊断
- 肯定/否定事实识别、跨文件冲突检测和冲突字段评分隔离
- 顾问采纳冲突证据、画像写回、自动重评估和裁决审计
- 五维、100 分制确定性评分及逐项证据
- 内置4个已核验官方来源的本地知识库
- 前端知识库管理、搜索、自定义条目新增/删除和官方来源保护
- 风险级知识检索、来源链接、原文摘要和匹配分
- 无知识依据时自动降级为“依据不足/人工确认”
- 对“资料缺失”和“不合规”的明确区分
- 风险清单、人工确认标记和 90 天行动计划
- 顾问批准或退回的审核状态机
- 结构化报告 API
- 浏览器打印和 PDF 报告导出
- Dify 工作流调用适配器和 Prompt 模板
- Dify失败自动降级、本地兜底和运行告警
- 工作流运行记录、成功率和平均耗时监控
- Redis最近任务状态、MySQL自动回退和基础设施就绪检查
- 30条场景评测的一键执行、分类通过率和失败项展示
- 可导入的 N8N Webhook 编排
- 30 条 AI 场景评测集
- FastAPI 自动化测试与 Vue 生产构建
- MySQL、Redis、N8N、前后端 Docker Compose 部署

## 架构

```text
Vue 3 ──HTTP──> FastAPI ──> MySQL
                    │       Redis（预留任务状态/缓存）
                    ├─────> Dify 工作流 / RAG（可选）
                    └─────> 本地确定性诊断（默认）

N8N ──Webhook──> FastAPI 诊断接口
```

设计原则：LLM 负责理解非结构化资料和生成建议；Python 代码负责评分、状态、校验和降级。没有模型密钥时，系统仍可完整演示。

## 一键启动

确保 Docker Desktop 已启动，在项目根目录执行：

```powershell
docker compose up --build
```

启动后访问：

- Web 工作台：http://localhost:5010
- API 文档：http://localhost:8010/docs
- 健康检查：http://localhost:8010/api/health
- N8N：http://localhost:5678
- MySQL：localhost:3310（容器内 3306；数据库 `green_advisor`，用户 `green_user`）
- Redis：localhost:6380（容器内 6379）

停止服务：

```powershell
docker compose down
```

如需同时删除本项目的数据库卷，请明确执行 `docker compose down -v`；该操作会删除容器中的演示数据。

## 本地开发

### 后端

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8010
```

后端本地默认使用 SQLite，避免强制安装 MySQL。Docker 环境自动切换到 MySQL。

运行测试：

```powershell
cd backend
python -m pytest -q
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

生产构建验证：

```powershell
npm run build
```

## 演示流程

1. 打开 Web 工作台，使用已经填好的储能企业数据创建诊断。
2. 查看绿色成熟度、资料完整度和五维评分。
3. 解释“资料缺失不等于不合规”的处理方式。
4. 展示风险依据、人工确认标记和 90 天计划。
5. 上传一份企业 TXT/PDF/Word/Excel 材料，展示解析结果。
6. 以顾问身份批准诊断，生成已完成状态。
7. 打开 `/api/projects/{id}/report` 展示结构化报告。
8. 检查每条风险下的“知识依据”，点击来源可访问官方页面。

左侧项目列表支持按企业/项目关键词搜索、按状态筛选。删除项目需要二次确认，并会同步删除评分、文档、证据、冲突、审核、运行记录、Redis任务状态及上传目录。

建议另外演示资料缺失和材料冲突两个案例，突出系统降级与人工审核能力。

标准演示资料位于 `demo/`：

```text
01-complete-company.txt     完整资料，预期100分
02-missing-information.txt 缺失资料，展示待确认项
03-conflict-a.txt           声明已完成碳盘查
03-conflict-b.txt           声明尚未开展碳盘查
```

一键端到端验收：

```powershell
python scripts\smoke_test.py
```

脚本会创建三类演示项目并验证上传、抽取、评分、冲突隔离、审核、PDF、评测和监控。

## Dify 配置

见 [workflows/dify/README.md](workflows/dify/README.md) 和 [Prompt 模板](workflows/dify/prompts.md)。复制 `.env.example` 为 `.env` 后配置：

```env
LLM_MODE=dify
DIFY_API_URL=https://你的-dify-host/v1
DIFY_API_KEY=app-xxxxxxxx
```

Dify 未配置时保持 `LLM_MODE=local`。密钥不要提交到 Git。

监控接口：

```text
GET /api/metrics/summary
GET /api/workflow-runs
GET /api/health/ready
GET /api/projects/{id}/task-status
```

页面顶部展示当前AI模式、累计运行、成功率、平均耗时和降级次数。Dify返回的画像字段只有携带原文证据时才会进入企业画像。

项目最近一次任务状态优先读取Redis；Redis不可用时自动读取MySQL中的 `workflow_runs`。Redis属于可降级组件，不会因缓存故障阻断诊断主链路。Docker健康检查会验证MySQL、Redis、后端和前端服务，而不仅检查容器是否处于Up状态。

## 本地知识库与引用

系统首次启动会写入4条短摘要及官方来源元数据：工信部绿色工厂、IFRS S1、GHG Protocol企业标准和英国政府CBAM政策摘要。仓库不复制整份标准或法规。

相关接口：

```text
GET  /api/knowledge
POST /api/knowledge
GET  /api/knowledge/search?q=英国CBAM商品编码
```

诊断时，每条风险会获得 `citations` 和 `evidence_status`。无匹配依据时，`evidence_status=insufficient`，且强制进入人工确认。

## N8N 配置

首次启动后可手动导入：

`workflows/n8n/green-advisor-orchestration.json`

当前 Docker 开发环境也可以通过以下命令直接导入：

```powershell
docker compose exec -T n8n n8n import:workflow --input=/workflows/green-advisor-orchestration.json
```

工作流接收 `project_id`，调用 FastAPI 诊断接口并返回结果。Docker 网络内使用 `http://backend:8010`；N8N 在宿主机单独运行时改为 `http://host.docker.internal:8010` 或 `http://localhost:8010`。

## 评测集

校验 30 条场景数据：

```powershell
python evaluation/validate_cases.py
```

评测集覆盖信息抽取、RAG 引用、资料缺失、材料冲突和报告生成。接入真实 Dify 后，可在这些用例上补充准确率、引用正确率、响应时间和调用成本统计。

也可以通过页面的“运行30条评测”按钮或API执行：

```text
POST /api/evaluations/run
```

当前规则基线在内置30条用例上为30/30；新增真实企业样本后应继续扩展评测集，不能把该结果解释为生产环境准确率。

## 关键目录

```text
backend/             FastAPI、数据模型、评分规则与测试
frontend/            Vue 3 工作台
workflows/dify/      Dify 接入说明与 Prompt
workflows/n8n/       N8N 可导入工作流
evaluation/          30 条评测用例
knowledge/           公开演示知识库说明
demo/                演示企业画像
scripts/             一键端到端冒烟测试
docs/                架构、演示指南、面试问答和简历描述
.github/workflows/   CI自动测试与构建
开发计划.txt         完整开发和验收计划
```

## 面试材料

- `docs/architecture.md`：系统架构和关键取舍
- `docs/demo-guide.md`：10分钟演示顺序
- `docs/interview-qa.md`：高频技术问答
- `docs/resume-description.md`：简历项目描述

## 当前边界

- 评分是演示规则，不代表专业认证结果。
- Dify 知识库需要根据合法公开资料在目标环境中创建。
- Redis 已纳入部署架构，当前同步 MVP 尚未引入不必要的任务队列。
- 登录、多租户、计费和生产级权限不在本次面试 MVP 范围内。
