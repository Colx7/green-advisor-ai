import json
from typing import Any

from redis import Redis

from .config import get_settings


class RuntimeState:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )

    def available(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def set_project_status(self, project_id: int, payload: dict[str, Any]) -> bool:
        try:
            self.client.setex(f"green-advisor:project:{project_id}:last-run", 86400, json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            return False

    def get_project_status(self, project_id: int) -> dict[str, Any] | None:
        try:
            value = self.client.get(f"green-advisor:project:{project_id}:last-run")
            return json.loads(value) if value else None
        except Exception:
            return None

    def delete_project_status(self, project_id: int) -> bool:
        try:
            self.client.delete(f"green-advisor:project:{project_id}:last-run")
            return True
        except Exception:
            return False


runtime_state = RuntimeState()
