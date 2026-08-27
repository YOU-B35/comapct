#!/usr/bin/env python3
"""CrossHub Sync Helper — 桌面窗口版（真·桌面应用）。

与运维常驻版 sync_helper_app.py 的区别：
- 双击 EXE 直接弹出原生桌面窗口（pywebview），不用再开浏览器
- 同时保留系统托盘图标、面板 Flask、健康检查、Agent 轮询
- 打包成 64 位 EXE + 自定义图标 + 版本资源 + 无控制台黑框

开发态运行：
  py backend/python/scripts/sync_helper_desktop.py
打包：
  powershell -File scripts/build-sync-helper-exe.ps1 -Desktop
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

from agent.desktop_launcher import (
    setup_logging,
    ensure_pythonpath,
    launch_desktop_window,
    load_config_with_env,
    validate_and_prepare_config,
    configure_ssl_warnings,
)

logger = logging.getLogger(__name__)

APP_NAME = "CrossHub Sync Helper"
DEFAULT_HEALTH_PORT = 18765
PANEL_PORT = 18766


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def load_config_light() -> dict:
    r"""轻量 config：优先同目录 config.json → %LOCALAPPDATA%\CrossHub\SyncHelper\config.json"""
    cfg: dict = {}
    candidates = [
        app_dir() / "config.json",
        Path(os.environ.get("LOCALAPPDATA", "")) / "CrossHub" / "SyncHelper" / "config.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                import json
                d = json.loads(p.read_text(encoding="utf-8-sig"))
                if isinstance(d, dict):
                    cfg.update(d)
                    break
            except Exception as e:
                logger.warning(f"Failed to load config from {p}: {e}")

    return load_config_with_env(cfg)


def main() -> int:
    # ⚠ 默认禁用（含生产部署）：桌面窗口版仅在用户明确设置 CROSSHUB_ALLOW_DESKTOP=1
    # 时才允许启动；日常请使用托盘浏览器版 scripts/sync_helper_app.py。
    if (os.environ.get("CROSSHUB_ALLOW_DESKTOP") or "").strip() not in {"1", "true", "True"}:
        print(
            "桌面窗口版默认禁用：设置环境变量 CROSSHUB_ALLOW_DESKTOP=1 后才可启动。"
            "日常请使用托盘浏览器版（scripts/sync_helper_app.py）。",
            file=sys.stderr,
        )
        return 2

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ensure_pythonpath()

    debug = os.environ.get("DEBUG", "").lower() in ("1", "true")
    setup_logging(debug=debug)
    configure_ssl_warnings()

    cfg = load_config_light()
    if not cfg:
        logger.error("No configuration found. Check config.json or env vars.")
        input("Press Enter to exit...")
        return 2

    # ── 依赖检查：pywebview 不可用则兜底浏览器 ──
    try:
        import webview  # noqa: F401
        have_webview = True
    except ImportError:
        have_webview = False
        logger.warning("pywebview not installed; will fall back to browser")

    from agent.tray_app import (
        start_panel_server,
        start_tray,
        PANEL_PORT,
        run_agent_loop,
        start_ops_notify_watcher,
        note_agent_loop_thread,
    )
    from agent.health_server import start_health_server

    stop_event = threading.Event()
    client = None
    if cfg.get("agent_token") and cfg.get("java_api_url"):
        try:
            from agent.java_client import AgentApiClient

            client = AgentApiClient(
                token=cfg["agent_token"].strip(),
                base_url=cfg["java_api_url"].rstrip("/"),
            )
            logger.info(f"Connected to {cfg['java_api_url']}")
        except Exception as e:
            logger.warning(f"AgentApiClient init failed: {e}")

    # 健康检查
    try:
        start_health_server(int(cfg.get("health_port") or DEFAULT_HEALTH_PORT))
    except OSError as e:
        logger.warning(f"Health server failed: {e}")

    # 面板服务（未绑定也可打开，用来录入绑定码）
    start_panel_server(client, stop_event)

    # 系统托盘（右键菜单：打开窗口 / 重启 Agent / 退出）
    start_tray(stop_event)

    # Agent 轮询 + 运维通知
    if client is not None:
        try:
            start_ops_notify_watcher(stop_event)
        except Exception as e:
            logger.warning(f"Ops notify watcher failed: {e}")

        t = threading.Thread(
            target=run_agent_loop, args=(client, stop_event), daemon=True, name="agent-loop"
        )
        t.start()
        note_agent_loop_thread(t, ops_started=True)
    else:
        note_agent_loop_thread(None, ops_started=False)

    url = f"http://127.0.0.1:{PANEL_PORT}/"
    logger.info(f"[{APP_NAME}] Panel ready: {url}")

    if have_webview:
        logger.info("Launching desktop window...")
        return launch_desktop_window(client, stop_event, panel_port=PANEL_PORT)
    else:
        logger.info(f"Opening in browser: {url}")
        import webbrowser
        webbrowser.open(url)
        stop_event.wait()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
