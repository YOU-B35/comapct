"""紫鸟开放平台 WebDriver HTTP API 封装。

文档: https://open.ziniao.com/docSupport?docId=98
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.ziniao.discovery import DEFAULT_CLIENT_PATH, discover_ziniao_client_path

DEFAULT_SOCKET_PORT = 16851


@dataclass
class ZiniaoConfig:
    company: str
    username: str
    password: str
    client_path: Path = DEFAULT_CLIENT_PATH
    socket_port: int = DEFAULT_SOCKET_PORT
    request_timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "ZiniaoConfig":
        """每次从环境变量 / 项目 .env 读取，避免冻结 exe 导入顺序导致空常量。"""
        cls._ensure_project_dotenv()
        company = (os.getenv("ZINIAO_COMPANY") or "").strip()
        username = (os.getenv("ZINIAO_USERNAME") or "").strip()
        password = (os.getenv("ZINIAO_PASSWORD") or "").strip()
        client_path = discover_ziniao_client_path((os.getenv("ZINIAO_CLIENT_PATH") or "").strip())
        socket_port = int(os.getenv("ZINIAO_SOCKET_PORT") or str(DEFAULT_SOCKET_PORT))

        if not company or not username or not password:
            raise ValueError(
                "请在 backend/python/.env 配置 ZINIAO_COMPANY、ZINIAO_USERNAME、ZINIAO_PASSWORD"
            )
        return cls(
            company=company,
            username=username,
            password=password,
            client_path=Path(client_path),
            socket_port=socket_port,
        )

    @staticmethod
    def _ensure_project_dotenv() -> None:
        if (os.getenv("ZINIAO_COMPANY") or "").strip() and (os.getenv("ZINIAO_USERNAME") or "").strip():
            return
        candidates: list[Path] = []
        project_root = (os.getenv("CROSSHUB_PROJECT_ROOT") or "").strip()
        if project_root:
            candidates.append(Path(project_root) / "backend" / "python" / ".env")
        try:
            from app.config import ROOT

            candidates.append(Path(ROOT) / ".env")
        except Exception:
            pass
        candidates.append(Path(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\python\.env"))
        for env_file in candidates:
            if not env_file.is_file():
                continue
            try:
                from dotenv import load_dotenv

                load_dotenv(env_file, override=False)
                return
            except Exception:
                continue



class ZiniaoClient:
    def __init__(self, config: ZiniaoConfig) -> None:
        self.config = config
        self.base_url = f"http://127.0.0.1:{config.socket_port}"

    def _auth_payload(self) -> dict[str, str]:
        return {
            "company": self.config.company,
            "username": self.config.username,
            "password": self.config.password,
        }

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {**self._auth_payload(), **payload}
        body.setdefault("requestId", str(uuid.uuid4()))
        with httpx.Client(timeout=self.config.request_timeout) as client:
            resp = client.post(f"{self.base_url}/api/browser/list", json=body)
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"紫鸟 API 返回非 JSON 对象: {data!r}")
        return data

    def _post_action(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {**self._auth_payload(), **payload}
        body.setdefault("requestId", str(uuid.uuid4()))
        with httpx.Client(timeout=self.config.request_timeout) as client:
            resp = client.post(f"{self.base_url}{endpoint}", json=body)
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"紫鸟 API 返回非 JSON 对象: {data!r}")
        return data

    def ping(self) -> bool:
        """检测 WebDriver HTTP 服务是否可用（需开发者模式，非普通 UI 模式）。"""
        try:
            payload = {
                **self._auth_payload(),
                "action": "getBrowserList",
                "requestId": str(uuid.uuid4()),
            }
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(f"{self.base_url}/api/browser/list", json=payload)
                if resp.status_code >= 500:
                    return False
                data = resp.json()
                # 能收到 JSON 且不是 socket 未就绪，即表示 WebDriver 模式已启动
                return isinstance(data, dict) and data.get("statusCode") is not None
        except httpx.HTTPError:
            return False

    def is_normal_client_running(self) -> bool:
        if not sys.platform.startswith("win"):
            return False
        try:
            import subprocess as sp

            ps = (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.Name -eq 'ziniao.exe' -and $_.CommandLine -notmatch 'web_driver' } | "
                "Select-Object -First 1 -ExpandProperty ProcessId"
            )
            out = sp.check_output(
                ["powershell", "-NoProfile", "-Command", ps],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            return bool(out)
        except Exception:
            return False

    def get_browser_list(self) -> list[dict[str, Any]]:
        data = self._post_action(
            "/api/browser/list",
            {"action": "getBrowserList"},
        )
        status = data.get("statusCode")
        if status != 0:
            raise RuntimeError(
                f"getBrowserList 失败 statusCode={status} err={data.get('err') or data.get('LastError')}"
            )
        browser_list = data.get("browserList") or []
        if not isinstance(browser_list, list):
            raise RuntimeError(f"browserList 格式异常: {browser_list!r}")
        return browser_list

    def start_browser(
        self,
        *,
        browser_id: str | None = None,
        browser_oauth: str | None = None,
        headless: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "startBrowser",
            "isHeadless": 1 if headless else 0,
            "runMode": 2,
            "cookieTypeLoad": 0,
            "cookieTypeSave": 0,
            "isLoadUserPlugin": True,
            "notPromptForDownload": 1,
        }
        if browser_id:
            payload["browserId"] = browser_id
        elif browser_oauth:
            payload["browserOauth"] = browser_oauth
        else:
            raise ValueError("browser_id 或 browser_oauth 至少提供一个")

        print(
            f"[Ziniao] startBrowser begin id={browser_id or '-'} oauth={'yes' if bool(browser_oauth) else 'no'} "
            f"headless={headless}",
            file=sys.stderr,
        )
        data = self._post_action("/api/browser/start", payload)
        status = data.get("statusCode")
        if status != 0:
            raise RuntimeError(
                f"startBrowser 失败 statusCode={status} err={data.get('err') or data.get('LastError')}"
            )
        debug_ref = data.get("debuggingPort") or data.get("ws") or "-"
        print(f"[Ziniao] startBrowser ok status={status} debug={debug_ref}", file=sys.stderr)
        return data

    def stop_browser(
        self,
        *,
        browser_id: str | None = None,
        browser_oauth: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": "stopBrowser"}
        if browser_id:
            payload["browserId"] = browser_id
        elif browser_oauth:
            payload["browserOauth"] = browser_oauth
        else:
            raise ValueError("browser_id 或 browser_oauth 至少提供一个")
        return self._post_action("/api/browser/stop", payload)

    def ensure_webdriver_client(self, wait_seconds: int = 15) -> None:
        if self.ping():
            print(f"[Ziniao] WebDriver already online: {self.base_url}", file=sys.stderr)
            return
        if self.is_normal_client_running():
            raise RuntimeError(
                "检测到紫鸟正在普通模式运行（无 WebDriver API）。"
                "请先完全退出紫鸟客户端，再以开发者模式启动："
                f'"{self.config.client_path}" --run_type=web_driver --ipc_type=http --port={self.config.socket_port}'
                "（或在紫鸟「设置 → 店铺 → 下载 WebDriver 启动器」）"
            )
        exe = self.config.client_path
        if not exe.exists():
            raise FileNotFoundError(f"未找到紫鸟客户端: {exe}")

        print(
            f"[Ziniao] starting WebDriver client path={exe} port={self.config.socket_port}",
            file=sys.stderr,
        )
        subprocess.Popen(
            [
                str(exe),
                "--run_type=web_driver",
                "--ipc_type=http",
                f"--port={self.config.socket_port}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self.ping():
                time.sleep(2)
                print(f"[Ziniao] WebDriver ready: {self.base_url}", file=sys.stderr)
                return
            time.sleep(1)
        raise TimeoutError(
            f"紫鸟 WebDriver 未在 {wait_seconds}s 内就绪。"
            f"请确认 Boss 已开通 WebDriver，并以开发者模式启动（端口 {self.config.socket_port}）"
        )
