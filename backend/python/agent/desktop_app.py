"""CrossHub Sync Helper — 桌面窗口模式。

用 pywebview 将 Flask 面板包装为原生桌面窗口，替代浏览器标签页。
启动后：
  1. Flask 面板服务（127.0.0.1:18766）
  2. 系统托盘常驻（与 tray_app 共用）
  3. Agent 心跳/轮询（已绑定时）
  4. pywebview 原生窗口（替代 webbrowser.open）

pywebview 未安装时自动回退到 tray_app 原有行为（托盘 + 浏览器打开面板）。
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any

from agent.desktop_launcher import (
    launch_desktop_window,
    configure_ssl_warnings,
    ensure_pythonpath,
    redirect_console_to_log,
)

logger = logging.getLogger(__name__)


def run_desktop_mode(cfg: dict[str, Any]) -> int:
    """桌面窗口模式主入口：面板 + 托盘 + Agent 轮询 + pywebview 窗口。

    与 sync_helper_app._try_start_tray_mode 平行，但用 pywebview 替代浏览器。
    cfg 由 sync_helper_app.load_config() 返回。
    """
    try:
        import pystray  # noqa: F401
        import flask  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:
        logger.error(f"Missing dependencies: {e} — skipping desktop mode")
        return 1

    from agent.tray_app import (
        start_panel_server,
        start_tray,
        run_agent_loop,
        start_ops_notify_watcher,
        note_agent_loop_thread,
        PANEL_PORT,
    )
    from agent.health_server import start_health_server
    from agent.config import AGENT_HEALTH_PORT

    client = None
    if cfg.get("bound") and (cfg.get("agent_token") or "").strip():
        try:
            from agent.java_client import AgentApiClient

            client = AgentApiClient(token=cfg.get("agent_token"), base_url=cfg.get("java_api_url"))
        except Exception as e:
            logger.warning(f"AgentApiClient initialization failed: {e}")

    stop_event = threading.Event()

    try:
        start_health_server(AGENT_HEALTH_PORT)
    except OSError as e:
        logger.warning(f"Health server startup failed: {e}")

    start_panel_server(client, stop_event)
    start_tray(stop_event)

    if client is not None:
        try:
            start_ops_notify_watcher(stop_event)
        except Exception as e:
            logger.warning(f"Ops notify watcher failed: {e}")

        agent_thread = threading.Thread(
            target=run_agent_loop, args=(client, stop_event), daemon=True, name="agent-loop"
        )
        agent_thread.start()
        note_agent_loop_thread(agent_thread, ops_started=True)
    else:
        logger.info("Not bound — Agent polling disabled. Login in panel to bind.")
        note_agent_loop_thread(None, ops_started=False)

    logger.info(f"Desktop mode started, panel: http://127.0.0.1:{PANEL_PORT}")
    logger.info("Close window or tray menu to exit.")

    return launch_desktop_window(client, stop_event, panel_port=PANEL_PORT)


if __name__ == "__main__":
    from scripts.sync_helper_app import load_config, setup_runtime_log
    from pathlib import Path

    cfg = load_config()
    if not cfg:
        input("按回车退出...")
        raise SystemExit(2)

    setup_runtime_log(str(cfg.get("project_root") or ""))

    # 如果运行在 pythonw 模式，重定向输出到日志文件
    project_root = cfg.get("project_root")
    if project_root:
        log_file = Path(project_root) / "logs" / "sync_helper_desktop.log"
        redirect_console_to_log(log_file)

    if cfg.get("start_ziniao", True) and cfg.get("bound"):
        from scripts.sync_helper_app import maybe_start_ziniao

        maybe_start_ziniao()
    elif not cfg.get("bound"):
        print("==> 未绑定，跳过紫鸟启动；请在桌面窗口内登录绑定")

    print(f"==> API: {cfg['java_api_url']}")
    if not cfg.get("bound"):
        print("    状态: 未绑定（仅面板可用）")

    if cfg.get("bound"):
        try:
            from agent.java_client import AgentApiClient
            from app.browser.profile_sync import pull_all_for_tenant

            client = AgentApiClient()
            tid = client.resolve_agent_tenant_id()
            if tid:
                pull_all_for_tenant(client, tid)
        except Exception as exc:
            print(f"    [WARN] Profile pull on startup skipped: {exc}")

    raise SystemExit(run_desktop_mode(cfg))
