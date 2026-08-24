"""临时启动器：演示 CrossHub Helper 桌面版（pywebview + 面板 Flask 服务）。

仅用于 UI 效果预览，不启动 Agent 轮询/紫鸟。依赖：pywebview / flask / pystray / pillow。
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

from agent.desktop_launcher import setup_logging, ensure_pythonpath, launch_desktop_window

logger = logging.getLogger(__name__)

# 确保 backend/python 在 sys.path
ensure_pythonpath()

import webview

from agent.tray_app import start_panel_server, start_tray, PANEL_PORT
from agent.health_server import start_health_server
from agent.config import AGENT_HEALTH_PORT


def main() -> int:
    setup_logging(debug=os.environ.get("DEBUG", "").lower() in ("1", "true"))

    stop_event = threading.Event()
    try:
        start_health_server(AGENT_HEALTH_PORT)
    except OSError as e:
        logger.warning(f"Health server failed: {e}")

    start_panel_server(None, stop_event)  # client=None → 未绑定演示模式，允许跳过绑定
    start_tray(stop_event)

    logger.info(f"Panel ready: http://127.0.0.1:{PANEL_PORT}")
    logger.info("Opening desktop window...")

    return launch_desktop_window(None, stop_event, panel_port=PANEL_PORT)


if __name__ == "__main__":
    raise SystemExit(main())
