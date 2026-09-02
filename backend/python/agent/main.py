#!/usr/bin/env python3
"""CrossHub Agent 常驻进程。"""
from __future__ import annotations

import socket
import sys
import threading
import time

from concurrent.futures import Future

from agent.config import (
    AGENT_DISPATCH_WORKERS,
    AGENT_HEALTH_PORT,
    HEARTBEAT_INTERVAL_SECONDS,
    POLL_INTERVAL_SECONDS,
    ZINIAO_SOCKET_PORT,
)
from agent.handlers import dispatch_task
from agent.health_server import start_health_server
from agent.java_client import AgentApiClient
from agent.task_executor import BrowserAffinityTaskExecutor
from app.ziniao.client import ZiniaoClient, ZiniaoConfig


def ziniao_port_open(port: int | None = None) -> bool:
    target_port = port or ZINIAO_SOCKET_PORT
    try:
        with socket.create_connection(("127.0.0.1", target_port), timeout=2):
            return True
    except OSError:
        return False


def create_ziniao_client() -> ZiniaoClient | None:
    try:
        return ZiniaoClient(ZiniaoConfig.from_env())
    except ValueError as exc:
        print(f"==> 紫鸟账号未配置，将仅检测 WebDriver 端口: {exc}", file=sys.stderr)
        return None


def detect_ziniao_online(ziniao: ZiniaoClient | None) -> bool:
    if not ziniao_port_open():
        return False
    if ziniao is None:
        return True
    try:
        return ziniao.ping()
    except Exception:
        # WebDriver 端口已开即视为就绪；凭据异常时仍允许页面显示紫鸟在线
        return True


def _heartbeat_loop(
    client: AgentApiClient,
    ziniao_holder: list[ZiniaoClient | None],
    stop_event: threading.Event,
) -> None:
    while not stop_event.is_set():
        try:
            ziniao_online = detect_ziniao_online(ziniao_holder[0])
            client.heartbeat(ziniao_online=ziniao_online)
        except Exception as exc:
            print(f"Agent 心跳失败: {exc}", file=sys.stderr)
        stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)


def main() -> int:
    try:
        client = AgentApiClient()
    except ValueError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 2

    try:
        start_health_server(AGENT_HEALTH_PORT)
        print(f"==> 本机健康检查: http://127.0.0.1:{AGENT_HEALTH_PORT}/health")
    except OSError as exc:
        print(f"==> 健康检查端口 {AGENT_HEALTH_PORT} 启动失败: {exc}", file=sys.stderr)

    print(
        f"==> CrossHub Agent 已启动，任务轮询 {POLL_INTERVAL_SECONDS}s，"
        f"心跳 {HEARTBEAT_INTERVAL_SECONDS}s，并行 worker={AGENT_DISPATCH_WORKERS}，"
        f"API {client.base_url}",
    )
    ziniao_holder: list[ZiniaoClient | None] = [create_ziniao_client()]
    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(client, ziniao_holder, stop_event),
        daemon=True,
    )
    heartbeat_thread.start()

    inflight: set[Future] = set()

    def _on_done(fut: Future) -> None:
        inflight.discard(fut)
        try:
            fut.result()
        except Exception as exc:  # noqa: BLE001
            print(f"Agent 任务执行失败: {exc}", file=sys.stderr)

    with BrowserAffinityTaskExecutor(
        max_workers=AGENT_DISPATCH_WORKERS,
        thread_name_prefix="agent-task",
    ) as pool:
        while True:
            try:
                # 清理已完成 future，避免集合膨胀
                done = {f for f in inflight if f.done()}
                for fut in done:
                    _on_done(fut)
                tasks = client.poll_tasks()
                _LOGIN_FIRST = {
                    "temu_login_open": 0,
                    "temu_frontend_login_open": 1,
                    "aliexpress_login_open": 0,
                    "1688_login_open": 0,
                    "1688_orders_sync": 30,
                    "1688_products_sync": 40,
                    "1688_peer_bestsellers_sync": 45,
                    "douyin_login_open": 0,
                }
                tasks = sorted(
                    tasks,
                    key=lambda t: _LOGIN_FIRST.get(str(t.get("task_type") or ""), 50),
                )
                for task in tasks:
                    print(f"==> 执行任务: {task.get('task_type')} ({task.get('task_id')})")
                    fut = pool.submit(dispatch_task, client, task)
                    inflight.add(fut)
                    fut.add_done_callback(lambda f: inflight.discard(f))
            except Exception as exc:
                print(f"Agent 轮询失败: {exc}", file=sys.stderr)

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
