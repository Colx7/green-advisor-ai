# Dify 接入说明

本项目默认使用本地确定性诊断，确保没有模型密钥时仍可完整运行。配置 Dify 后，后端通过 `DifyClient` 调用工作流 API。

## 建议创建的三个工作流

1. `company-profile-extraction`：输入 `document_text`，输出符合企业画像 Schema 的 JSON。
2. `risk-analysis-rag`：输入 `company_profile`，检索绿色政策知识库，输出风险、引用和置信度。
3. `action-report-generation`：输入已审核风险，输出 90 天行动计划和报告章节。

当前后端已接通第一个工作流。输入变量必须命名为 `document_text`，结束节点必须输出：

```json
{
  "profile": {
    "carbon_inventory": true
  },
  "evidence": [
    {
      "field": "carbon_inventory",
      "value": true,
      "filename": "企业报告.pdf",
      "excerpt": "2025年完成范围一和范围二温室气体盘查",
      "confidence": 0.91
    }
  ]
}
```

没有对应原文证据的字段会被后端丢弃。Dify超时、网络失败、输出格式错误或缺少证据时，系统自动使用本地抽取，并记录一条 `degraded` 运行记录。

## 环境变量

```env
LLM_MODE=dify
DIFY_API_URL=https://你的-dify-host/v1
DIFY_API_KEY=app-xxxxxxxx
```

修改 `.env` 后执行 `docker compose up -d --force-recreate backend` 使配置生效。

不要提交真实 API Key。Dify 不可用时把 `LLM_MODE` 改回 `local`。

## 知识库元数据

每份资料至少标记：`title`、`topic`、`industry`、`region`、`published_at`、`source_url`。风险结论必须返回文档标题和原文片段；没有有效引用时输出 `insufficient_evidence=true`。
