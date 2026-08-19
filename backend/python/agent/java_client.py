"""Java Agent API 客户端。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from agent.config import AGENT_TOKEN, JAVA_API_URL


def _resolve_java_api_url(base_url: str | None = None) -> str:
    """Prefer live process env over module snapshot (load_config may update env later)."""
    if base_url and str(base_url).strip():
        return str(base_url).strip().rstrip("/")
    env = (os.environ.get("JAVA_API_URL") or "").strip().rstrip("/")
    if env:
        return env
    try:
        import agent.config as agent_config

        snap = str(getattr(agent_config, "JAVA_API_URL", "") or "").strip().rstrip("/")
        if snap:
            return snap
    except Exception:
        pass
    return (JAVA_API_URL or "https://www.yoto.work").rstrip("/")


class AgentApiClient:
    def __init__(self, token: str | None = None, base_url: str | None = None) -> None:
        self.base_url = _resolve_java_api_url(base_url)
        env_token = (os.environ.get("AGENT_TOKEN") or "").strip()
        self.token = (token or env_token or AGENT_TOKEN).strip()
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

    def ingest_douyin_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/douyin/orders/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_douyin_products(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/douyin/products/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_1688_products(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/1688/products/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_1688_orders(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/1688/orders/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_1688_peer_bestsellers(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/1688/peer-bestsellers/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_douyin_compass(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/douyin/compass/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_douyin_opportunity(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/douyin/opportunity/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_douyin_compass_product_rank(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/douyin/compass-product-rank/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def ingest_douyin_issues(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/douyin/issues/ingest",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("data") if isinstance(body, dict) else {}

    def report_temu_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Push Temu seller session snapshot while login window is still open."""
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/api/agent/temu/session-snapshot",
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

    def resolve_agent_tenant_id(self) -> int | None:
        env_tid = (os.environ.get("AGENT_TENANT_ID") or "").strip()
        if env_tid.isdigit():
            return int(env_tid)
        for cfg_path in self._config_paths():
            try:
                payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for key in ("agent_tenant_id", "tenant_id"):
                value = payload.get(key)
                if value is not None and str(value).strip().isdigit():
                    return int(str(value).strip())
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{self.base_url}/api/agent/heartbeat",
                    headers=self._headers(),
                    json={"ziniao_online": False},
                )
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data") if isinstance(body, dict) else {}
                if isinstance(data, dict):
                    tid = data.get("tenant_id")
                    if tid is not None and str(tid).strip().isdigit():
                        return int(str(tid).strip())
        except Exception:
            return None
        return None

    def _config_paths(self) -> list[Path]:
        paths: list[Path] = []
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            paths.append(Path(local) / "CrossHub" / "SyncHelper" / "config.json")
        try:
            import sys

            if getattr(sys, "frozen", False):
                paths.insert(0, Path(sys.executable).resolve().parent / "config.json")
        except Exception:
            pass
        return paths

    def upload_profile(
        self,
        platform: str,
        tenant_id: int,
        session_key: str,
        bundle: bytes,
        *,
        if_match: str = "",
    ) -> dict[str, Any]:
        headers = {
            "X-Agent-Token": self.token,
            "Content-Type": "application/zip",
        }
        if if_match:
            headers["If-Match"] = if_match
        with httpx.Client(timeout=120.0) as client:
            resp = client.put(
                f"{self.base_url}/api/agent/profiles/{platform}/{tenant_id}/{session_key}",
                headers=headers,
                content=bundle,
            )
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data") if isinstance(body, dict) else {}
            return data if isinstance(data, dict) else {}

    def download_profile(
        self,
        platform: str,
        tenant_id: int,
        session_key: str,
        *,
        if_none_match: str = "",
    ) -> tuple[bytes | None, str]:
        headers = {"X-Agent-Token": self.token}
        if if_none_match:
            headers["If-None-Match"] = if_none_match
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(
                f"{self.base_url}/api/agent/profiles/{platform}/{tenant_id}/{session_key}",
                headers=headers,
            )
            if resp.status_code == 304:
                return None, resp.headers.get("ETag", if_none_match)
            if resp.status_code == 404:
                return None, ""
            resp.raise_for_status()
            return resp.content, resp.headers.get("ETag", "")

    def head_profile(
        self,
        platform: str,
        tenant_id: int,
        session_key: str,
    ) -> tuple[int, str]:
        headers = {"X-Agent-Token": self.token}
        with httpx.Client(timeout=30.0) as client:
            resp = client.head(
                f"{self.base_url}/api/agent/profiles/{platform}/{tenant_id}/{session_key}",
                headers=headers,
            )
            return resp.status_code, resp.headers.get("ETag", "")

    def list_profiles(self, platform: str, tenant_id: int) -> list[dict[str, Any]]:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{self.base_url}/api/agent/profiles/{platform}/{tenant_id}",
                headers=self._headers(),
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data") if isinstance(body, dict) else []
            return data if isinstance(data, list) else []

    def list_platform_accounts(self, tenant_id: int) -> dict[str, list[dict[str, Any]]]:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{self.base_url}/api/agent/platform-accounts",
                headers=self._headers(),
                params={"tenant_id": tenant_id},
            )
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data") if isinstance(body, dict) else {}
            return data if isinstance(data, dict) else {}
