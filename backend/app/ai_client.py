import json
from typing import Any

import httpx

from .config import get_settings


class DifyClient:
    """Dify 工作流适配器；未配置时由调用方继续使用本地确定性流程。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.dify_api_url and self.settings.dify_api_key)

    def run_workflow(self, inputs: dict[str, Any], user: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Dify 尚未配置")
        url = f"{self.settings.dify_api_url.rstrip('/')}/workflows/run"
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.settings.dify_api_key}"},
            json={"inputs": inputs, "response_mode": "blocking", "user": user},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def extract_profile(self, document_text: str, user: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        payload = self.run_workflow({"document_text": document_text}, user)
        outputs = payload.get("data", {}).get("outputs", {})
        profile = outputs.get("profile") or outputs.get("company_profile") or outputs.get("extracted_profile")
        evidence = outputs.get("evidence")
        if isinstance(profile, str):
            profile = json.loads(profile)
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        if not isinstance(profile, dict) or not profile:
            raise ValueError("Dify 工作流未返回有效的企业画像")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Dify 工作流未返回可追溯证据")
        normalized_evidence = []
        for item in evidence:
            if not isinstance(item, dict) or not item.get("field") or not item.get("excerpt"):
                continue
            normalized_evidence.append(
                {
                    "field": item["field"],
                    "value": item.get("value", profile.get(item["field"])),
                    "filename": item.get("filename", "Dify 综合抽取"),
                    "excerpt": str(item["excerpt"])[:240],
                    "confidence": float(item.get("confidence", 0.8)),
                    "method": "dify-workflow",
                }
            )
        evidenced_fields = {item["field"] for item in normalized_evidence}
        safe_profile = {key: value for key, value in profile.items() if key in evidenced_fields}
        if not safe_profile:
            raise ValueError("Dify 返回字段缺少对应证据")
        return safe_profile, normalized_evidence
