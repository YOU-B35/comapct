#!/usr/bin/env python3
"""CrossHub Sync Helper — 本机浏览器同步常驻程序（运维机 .exe，不对运营前端暴露）。

用法（开发）：
  set AGENT_TOKEN=...
  set JAVA_API_URL=https://www.yoto.work
  py backend/python/scripts/sync_helper_app.py

打包：
  powershell -File scripts/build-sync-helper-exe.ps1
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


APP_NAME = "CrossHub Sync Helper"
DEFAULT_HEALTH_PORT = 18765
DEFAULT_ZINIAO_PORT = 16851
ZINIAO_EXE = Path(r"C:\Program Files\ziniao\ziniao.exe")


class _TeeStream:
    def __init__(self, original, log_file) -> None:
        self._original = original
        self._log_file = log_file

    def write(self, data):
        try:
            self._original.write(data)
        except Exception:
            pass
        try:
            self._log_file.write(data)
            self._log_file.flush()
        except Exception:
            pass
        return len(data) if isinstance(data, str) else 0

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass
        try:
            self._log_file.flush()
        except Exception:
            pass


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def ensure_pythonpath() -> None:
    """开发态把 backend/python 加入 path；打包态由 PyInstaller 收集。"""
    if getattr(sys, "frozen", False):
        return
    root = Path(__file__).resolve().parents[1]  # backend/python
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    os.environ.setdefault("PYTHONPATH", root_str)


def load_config() -> dict:
    """优先：环境变量 → 同目录 config.json → %LOCALAPPDATA%\\CrossHub\\SyncHelper\\config.json"""
    cfg: dict = {}
    candidates = [
        app_dir() / "config.json",
        Path(os.environ.get("LOCALAPPDATA", "")) / "CrossHub" / "SyncHelper" / "config.json",
    ]
    for path in candidates:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    cfg.update(data)
                    print(f"==> 已加载配置: {path}")
                    break
            except Exception as exc:
                print(f"==> 读取配置失败 {path}: {exc}", file=sys.stderr)

    token = (os.environ.get("AGENT_TOKEN") or cfg.get("agent_token") or cfg.get("token") or "").strip()
    api = (os.environ.get("JAVA_API_URL") or cfg.get("java_api_url") or cfg.get("api_url") or "").strip()
    health = int(os.environ.get("AGENT_HEALTH_PORT") or cfg.get("health_port") or DEFAULT_HEALTH_PORT)
    start_ziniao = bool(cfg.get("start_ziniao", True))
    if os.environ.get("CROSSHUB_START_ZINIAO", "").strip() != "":
        start_ziniao = os.environ.get("CROSSHUB_START_ZINIAO", "1").strip() not in {"0", "false", "False"}

    if not token:
        print(
            f"[{APP_NAME}] 缺少 agent_token。\n"
            f"请在 {app_dir() / 'config.json'} 写入：\n"
            '  { "agent_token": "...", "java_api_url": "https://..." }\n'
            "或由运维用 scripts/setup-sync-helper-config.ps1 生成。",
            file=sys.stderr,
        )
        try:
            input("按回车退出...")
        except EOFError:
            pass
        return {}

    if not api:
        # 默认线上后端；禁止静默回落本地 Java（真实联调铁律）
        api = "https://www.yoto.work"

    # Profile / Cookie：必须指向历史目录，禁止用 _internal 下空 Profile
    project_root = (
        os.environ.get("CROSSHUB_PROJECT_ROOT")
        or cfg.get("project_root")
        or ""
    ).strip()
    if not project_root:
        for candidate in (
            Path(r"D:\NIUBI\SaaS-HZ_WEB_Demo"),
            app_dir().parent.parent.parent,  # dist/.../exe → 尝试向上找
            app_dir(),
        ):
            py_root = Path(candidate) / "backend" / "python"
            if (py_root / ".temu-browser-profile").is_dir() or (py_root / ".env").is_file():
                project_root = str(Path(candidate))
                break

    # 无论是否找到 profile，都尽量注入项目 .env（紫鸟 ZINIAO_* 等）
    env_candidates = []
    if project_root:
        os.environ["CROSSHUB_PROJECT_ROOT"] = project_root
        py_root = Path(project_root) / "backend" / "python"
        temu_profile = (
            os.environ.get("TEMU_PROFILE_ROOT")
            or cfg.get("temu_profile_root")
            or str(py_root / ".temu-browser-profile")
        )
        ae_profile = (
            os.environ.get("AE_PROFILE_ROOT")
            or cfg.get("ae_profile_root")
            or str(py_root / ".aliexpress-browser-profile")
        )
        os.environ["TEMU_PROFILE_ROOT"] = str(Path(temu_profile))
        os.environ["AE_PROFILE_ROOT"] = str(Path(ae_profile))
        env_candidates.append(py_root / ".env")
        print(f"==> project_root: {project_root}")
        print(f"==> temu_profile: {os.environ['TEMU_PROFILE_ROOT']}")
    env_candidates.append(Path(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\python\.env"))
    for env_file in env_candidates:
        if not env_file.is_file():
            continue
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
            print(f"==> 已加载 .env: {env_file}")
            break
        except Exception as exc:
            print(f"==> 加载 .env 失败 {env_file}: {exc}", file=sys.stderr)
    ziniao_ok = bool(
        (os.environ.get("ZINIAO_COMPANY") or "").strip()
        and (os.environ.get("ZINIAO_USERNAME") or "").strip()
        and (os.environ.get("ZINIAO_PASSWORD") or "").strip()
    )
    print(f"==> 紫鸟账号配置: {'已就绪' if ziniao_ok else '缺失（Amazon 将失败）'}")

    os.environ["AGENT_TOKEN"] = token
    os.environ["JAVA_API_URL"] = api.rstrip("/")
    os.environ["AGENT_HEALTH_PORT"] = str(health)
    return {
        "agent_token": token,
        "java_api_url": api.rstrip("/"),
        "health_port": health,
        "start_ziniao": start_ziniao,
        "project_root": project_root,
        "temu_profile_root": os.environ.get("TEMU_PROFILE_ROOT", ""),
        "ziniao_configured": ziniao_ok,
    }


def port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def maybe_start_ziniao() -> None:
    print("==> [1/2] Ziniao WebDriver（Amazon，端口 16851）...")
    if not ZINIAO_EXE.is_file():
        print("    [SKIP] 未安装紫鸟。Amazon 同步需要；Temu 不受影响。")
        return
    if port_listening(DEFAULT_ZINIAO_PORT):
        print("    紫鸟 WebDriver 已在运行。")
        return
    try:
        subprocess.Popen(
            [str(ZINIAO_EXE), "--run_type=web_driver", "--ipc_type=http", f"--port={DEFAULT_ZINIAO_PORT}"],
            cwd=str(ZINIAO_EXE.parent),
        )
        print("    正在启动紫鸟 WebDriver...")
        for _ in range(16):
            time.sleep(1)
            if port_listening(DEFAULT_ZINIAO_PORT):
                print("    紫鸟 WebDriver 就绪。")
                return
        print("    [WARN] 16851 未监听，Amazon 可能失败；Temu 仍可工作。")
    except Exception as exc:
        print(f"    [WARN] 启动紫鸟失败: {exc}", file=sys.stderr)


def setup_runtime_log(project_root: str) -> None:
    try:
        root = Path(project_root) if project_root else app_dir()
        log_dir = root / "backend" / "python" / "exports" / "agent-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "helper-runtime.log"
        fh = open(log_file, "a", encoding="utf-8")
        banner = f"\n=== helper session start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        fh.write(banner)
        fh.flush()
        sys.stdout = _TeeStream(sys.stdout, fh)
        sys.stderr = _TeeStream(sys.stderr, fh)
        print(f"==> 运行日志文件: {log_file}")
    except Exception as exc:
        print(f"==> [WARN] 初始化运行日志失败: {exc}", file=sys.stderr)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print(f"==> {APP_NAME}")
    print(f"==> 目录: {app_dir()}")
    ensure_pythonpath()
    cfg = load_config()
    if not cfg:
        input("按回车退出...")
        return 2
    setup_runtime_log(str(cfg.get("project_root") or ""))

    if cfg.get("start_ziniao", True):
        maybe_start_ziniao()
    else:
        print("==> [1/2] 跳过紫鸟启动（config.start_ziniao=false）")

    print("==> [2/2] 启动同步 Agent（Temu / 速卖通任务 / Amazon）...")
    print(f"    API: {cfg['java_api_url']}")
    print(f"    Health: http://127.0.0.1:{cfg['health_port']}/health")

    try:
        from agent.java_client import AgentApiClient
        from app.browser.profile_sync import pull_all_for_tenant

        client = AgentApiClient()
        tid = client.resolve_agent_tenant_id()
        if tid:
            pull_all_for_tenant(client, tid)
    except Exception as exc:
        print(f"    [WARN] Profile pull on startup skipped: {exc}")

    # ── 尝试托盘模式（需要 pystray + flask + pillow）──────────────────────
    _tray_ok = _try_start_tray_mode(cfg)

    if not _tray_ok:
        print("    [INFO] 托盘模式不可用，使用纯控制台模式。")
        print("    请保持本窗口打开。全平台日批由服务端 09:30 下发，本程序负责在本机开浏览器执行。")
        print()
        from agent.main import main as agent_main
        while True:
            code = agent_main()
            if code == 0:
                print("==> Agent 正常退出。")
                return 0
            print(f"==> Agent 异常退出 code={code}，5 秒后重试...", file=sys.stderr)
            time.sleep(5)

    return 0


def _try_start_tray_mode(cfg: dict) -> bool:
    """尝试启动托盘+面板模式。返回 True 表示已接管主线程（阻塞直到退出）。"""
    try:
        import pystray  # noqa: F401
        import flask    # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:
        print(f"    [SKIP] 缺少依赖 ({e})，跳过托盘模式。")
        return False

    try:
        from agent.tray_app import (
            _AppState, start_panel_server, start_tray, run_agent_loop,
            PANEL_PORT,
        )
        from agent.java_client import AgentApiClient
        from agent.health_server import start_health_server
        from agent.config import AGENT_HEALTH_PORT
        import threading
        import webbrowser

        client = AgentApiClient()
        stop_event = threading.Event()

        # 健康检查服务
        try:
            start_health_server(AGENT_HEALTH_PORT)
        except OSError:
            pass

        # Web 面板
        start_panel_server(client, stop_event)

        # 托盘图标
        start_tray(stop_event)

        # Agent 轮询线程
        agent_thread = threading.Thread(
            target=run_agent_loop, args=(client, stop_event), daemon=True, name="agent-loop"
        )
        agent_thread.start()

        # 延迟 1.5s 自动打开面板
        def _open_later():
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{PANEL_PORT}")
        threading.Thread(target=_open_later, daemon=True).start()

        print(f"==> 托盘模式已启动，面板: http://127.0.0.1:{PANEL_PORT}")
        print("    最小化到系统托盘即可常驻，右键托盘图标可打开面板或退出。")

        # 等待 stop_event（用户点托盘「退出」）
        stop_event.wait()
        print("==> 用户退出。")
        return True

    except Exception as exc:
        print(f"    [WARN] 托盘模式启动失败: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    raise SystemExit(main())
