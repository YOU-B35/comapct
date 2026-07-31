#!/usr/bin/env python3
"""CrossHub Sync Helper 应用入口。

同时启动：
1. 系统托盘
2. 本地 Web 面板 (FastAPI, port 19090)
3. Agent 轮询循环
4. 定时爬取调度器
"""
from __future__ import annotations

import sys
import threading
import webbrowser

# 确保项目根目录在 sys.path 中
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_web_server(stop_event: threading.Event):
    """在子线程中运行 FastAPI。"""
    import uvicorn

    from helper_app.web.server import app

    config = uvicorn.Config(app, host="127.0.0.1", port=19090, log_level="warning")
    server = uvicorn.Server(config)

    # uvicorn 没有原生 stop_event 支持，用 install_signal_handlers=False
    server.install_signal_handlers = lambda: None

    thread_server = threading.Thread(target=server.run, daemon=True, name="web")
    thread_server.start()
    stop_event.wait()
    server.should_exit = True


def _run_agent_loop(stop_event: threading.Event):
    """Agent 轮询循环（复用 agent.main 逻辑）。"""
    import time

    from agent.config import HEARTBEAT_INTERVAL_SECONDS, POLL_INTERVAL_SECONDS
    from agent.handlers import dispatch_task
    from agent.java_client import AgentApiClient

    try:
        client = AgentApiClient()
    except ValueError as exc:
        print(f"[Agent] 配置错误（跳过轮询）: {exc}", file=sys.stderr)
        return

    print(
        f"[Agent] 轮询已启动，间隔 {POLL_INTERVAL_SECONDS}s，API {client.base_url}"
    )

    def _heartbeat():
        while not stop_event.is_set():
            try:
                client.heartbeat()
            except Exception:
                pass
            stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)

    threading.Thread(target=_heartbeat, daemon=True, name="heartbeat").start()

    while not stop_event.is_set():
        try:
            tasks = client.poll_tasks()
            for task in tasks:
                print(f"[Agent] 执行任务: {task.get('task_type')} ({task.get('task_id')})")
                dispatch_task(client, task)
        except Exception as exc:
            print(f"[Agent] 轮询失败: {exc}", file=sys.stderr)
        stop_event.wait(POLL_INTERVAL_SECONDS)


def main() -> int:
    stop_event = threading.Event()

    # 1. Web 服务
    web_thread = threading.Thread(
        target=_run_web_server, args=(stop_event,), daemon=True, name="web-launcher"
    )
    web_thread.start()

    # 2. Agent 轮询
    agent_thread = threading.Thread(
        target=_run_agent_loop, args=(stop_event,), daemon=True, name="agent"
    )
    agent_thread.start()

    # 3. 定时调度器
    from helper_app.scheduler import start_scheduler

    start_scheduler(stop_event)

    # 4. 系统托盘（阻塞主线程）
    try:
        from helper_app.tray import start_tray

        def _on_quit():
            stop_event.set()

        tray_thread = start_tray(_on_quit)
        print("[Helper] CrossHub Sync Helper 已启动")
        print(f"[Helper] 面板地址: http://127.0.0.1:19090")

        # 首次启动自动打开浏览器
        webbrowser.open("http://127.0.0.1:19090")

        # 等待退出信号
        stop_event.wait()
    except ImportError:
        # 如果 pystray 不可用，回退为控制台模式
        print("[Helper] pystray 不可用，以控制台模式运行")
        print("[Helper] 面板地址: http://127.0.0.1:19090")
        print("[Helper] Ctrl+C 退出")
        try:
            stop_event.wait()
        except KeyboardInterrupt:
            stop_event.set()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
