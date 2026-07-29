"""Java Agent API 客户端。"""
from __future__ import annotations

import time
from typing import Any

import httpx

from agent.config import AGENT_TOKEN, JAVA_API_URL


class AgentApiClient:
    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self.base_url = (base_url or JAVA_API_URL).rstrip("/")
        self.token = (token or AGENT_TOKEN).strip()
        if not self.token:
            raise ValueError(
                "同步助手尚未配置。请到 CrossHub 下载并双击「CrossHub-Sync-Helper.bat」启动文件（Temu/Amazon 共用）。"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "X-Agent-Token": self.token,
            "Content-Type": "application/json",
        }

    def heartbeat(self, *, ziniao_online: bool) -> dict[str, Any]:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/heartbeat",
                headers=self._headers(),
                json={"ziniao_online": ziniao_online},
            )
            resp.raise_for_status()
            return resp.json()

    def poll_tasks(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{self.base_url}/api/agent/tasks",
                headers=self._headers(),
            )
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data")
            return data if isinstance(data, list) else []

    def ingest_temu(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/temu/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def complete_task(
        self,
        task_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> dict[str, Any]:
        body = {
            "status": status,
            "result": result or {},
            "error_code": error_code,
            "error_message": error_message,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/tasks/{task_id}/complete",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    def complete_task_with_retry(
        self,
        task_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error_code: str = "",
        error_message: str = "",
        attempts: int = 3,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return self.complete_task(
                    task_id,
                    status=status,
                    result=result,
                    error_code=error_code,
                    error_message=error_message,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(min(2 ** attempt, 8))
        if last_error:
            raise last_error
        raise RuntimeError("complete_task_with_retry failed without error")
