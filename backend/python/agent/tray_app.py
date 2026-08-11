"""CrossHub Sync Helper — 系统托盘 + 本地 Web 面板。

启动后在系统托盘常驻，右键可打开面板/退出。
面板地址：http://127.0.0.1:18766
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

# ─── 可选依赖，无 pystray/PIL 时退化为纯控制台 ──────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw

    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False

try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask.logging import default_handler

    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False

PANEL_PORT = int(os.environ.get("CROSSHUB_PANEL_PORT", "18766"))

def _locate_panel_dir() -> Path:
    """打包后 panel/ 在 sys._MEIPASS/agent/panel；开发态在源码旁。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "agent" / "panel"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "panel"

_PANEL_DIR = _locate_panel_dir()


# ─── 全局状态（线程共享）──────────────────────────────────────────────────────
class _AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.agent_status: str = "starting"  # starting | running | error
        self.last_error: str = ""
        self.last_task: str = ""
        self.last_sync_at: str = ""
        self.accounts: list[dict[str, Any]] = []
        self.syncing: set[str] = set()   # session_key 集合
        self.logging_in: set[str] = set()

    def update_agent(self, status: str, error: str | None = None, task: str = "") -> None:
        with self.lock:
            self.agent_status = status
            # error=None → 保留；error="" → 清空（恢复 running 时用）
            if error is not None:
                self.last_error = error
            if task:
                self.last_task = task
            if status == "running" and error is None:
                # 轮询恢复正常时清掉开机期残留的连接错误，避免面板一直像「异常」
                self.last_error = ""

    def set_accounts(self, accs: list[dict]) -> None:
        with self.lock:
            self.accounts = accs

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "agent_status": self.agent_status,
                "last_error": self.last_error,
                "last_task": self.last_task,
                "last_sync_at": self.last_sync_at,
                "accounts": list(self.accounts),
                "syncing": list(self.syncing),
                "logging_in": list(self.logging_in),
            }


_state = _AppState()


# ─── Flask 面板服务器 ──────────────────────────────────────────────────────────
def _build_flask_app(java_client: Any) -> "Flask":
    app = Flask(__name__, static_folder=None)
    app.logger.removeHandler(default_handler)

    @app.route("/")
    def index():
        html = _PANEL_DIR / "index.html"
        if html.is_file():
            return send_from_directory(str(_PANEL_DIR), "index.html")
        return "<h2>CrossHub Sync Helper</h2><p>panel/index.html missing</p>", 200

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(str(_PANEL_DIR), filename)

    def _helper_config_path():
        """Canonical config.json for tray bind GET/POST/DELETE + status (same as sync_helper_app)."""
        from agent.bind import default_config_path

        return default_config_path()

    @app.route("/api/status")
    def api_status():
        snap = _state.snapshot()
        try:
            from agent.bind import binding_status

            bind = binding_status(config_path=_helper_config_path())
            snap["bound"] = bool(bind.get("bound"))
            snap["bind"] = bind
        except Exception:
            snap["bound"] = bool((os.environ.get("AGENT_TOKEN") or "").strip())
            snap["bind"] = {}
        return jsonify(snap)

    @app.route("/api/bind", methods=["GET"])
    def api_bind_status():
        from agent.bind import binding_status
        from agent.machine_id import machine_fingerprint

        st = binding_status(config_path=_helper_config_path())
        st["fingerprint_preview"] = (machine_fingerprint() or "")[:12]
        return jsonify({"ok": True, **st})

    @app.route("/api/bind", methods=["POST"])
    def api_bind_enroll():
        """Consume website bind code → persist agent_token to config.json."""
        body = request.get_json(silent=True) or {}
        code = (body.get("code") or "").strip()
        display_name = (body.get("display_name") or "").strip()
        if not code:
            return jsonify({"ok": False, "msg": "请输入绑定码"}), 400
        try:
            from agent.bind import consume_bind_code

            result = consume_bind_code(
                code,
                display_name=display_name,
                config_path=_helper_config_path(),
                base_url=_api_base() or None,
            )
            _state.update_agent("running", error="")
            return jsonify({"ok": True, "msg": "绑定成功，请重启助手以开始同步", "data": result})
        except Exception as exc:
            return jsonify({"ok": False, "msg": str(exc)}), 400

    @app.route("/api/bind", methods=["DELETE"])
    def api_bind_clear():
        """Clear enrollment so another CrossHub account can re-bind on this PC."""
        try:
            from agent.bind import clear_binding

            result = clear_binding(config_path=_helper_config_path())
            _state.update_agent("starting", error="已清除绑定，请重新填入绑定码")
            return jsonify({"ok": True, "msg": "已清除绑定，可重新填入绑定码", "data": result})
        except Exception as exc:
            return jsonify({"ok": False, "msg": str(exc)}), 500

    @app.route("/api/tenants")
    def api_tenants():
        """从 Java 拉取所有租户列表。"""
        tenants = _fetch_tenants()
        return jsonify({"tenants": tenants})

    @app.route("/api/platform-accounts", methods=["GET"])
    def api_platform_accounts():
        """从 Java 拉取指定租户下所有平台的绑定账号。"""
        tenant_id = request.args.get("tenant_id", "")
        if not tenant_id:
            return jsonify({"error": "缺少 tenant_id"}), 400
        data = _fetch_platform_accounts(tenant_id)
        return jsonify({"platforms": data})

    @app.route("/api/ops/messages", methods=["GET"])
    def api_ops_messages():
        tenant_id_raw = request.args.get("tenant_id", "")
        try:
            tenant_id = int(tenant_id_raw)
        except (TypeError, ValueError):
            tenant_id = 0
        if tenant_id <= 0:
            return jsonify({"ok": False, "msg": "缺少 tenant_id"}), 400
        items, unread = _fetch_ops_messages(tenant_id)
        return jsonify({"ok": True, "items": items, "unread": unread})

    @app.route("/api/platform-accounts", methods=["POST"])
    def api_bind_platform_account():
        """Helper 绑定店铺 → 写入 Java platform_account（与 Boss 账户绑定同源）。"""
        body = request.get_json(silent=True) or {}
        tenant_id = body.get("tenant_id")
        if not tenant_id:
            return jsonify({"ok": False, "msg": "缺少 tenant_id"}), 400
        try:
            import httpx
            resp = httpx.post(
                f"{_api_base()}/api/agent/platform-accounts",
                headers=_api_headers(),
                json=body,
                timeout=20,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                msg = data.get("msg") or data.get("message") or data.get("error") or f"HTTP {resp.status_code}"
                return jsonify({"ok": False, "msg": msg}), resp.status_code
            return jsonify({"ok": True, "msg": data.get("message") or "绑定成功", "data": data.get("data")})
        except Exception as exc:
            return jsonify({"ok": False, "msg": str(exc)}), 500

    @app.route("/api/platform-accounts/<account_id>", methods=["DELETE"])
    def api_delete_platform_account(account_id: str):
        tenant_id = request.args.get("tenant_id", "")
        if not tenant_id:
            return jsonify({"ok": False, "msg": "缺少 tenant_id"}), 400
        try:
            import httpx
            resp = httpx.delete(
                f"{_api_base()}/api/agent/platform-accounts/{account_id}",
                params={"tenant_id": tenant_id},
                headers=_api_headers(),
                timeout=20,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400:
                msg = data.get("msg") or data.get("message") or f"HTTP {resp.status_code}"
                return jsonify({"ok": False, "msg": msg}), resp.status_code
            return jsonify({"ok": True, "msg": data.get("message") or "已解除绑定"})
        except Exception as exc:
            return jsonify({"ok": False, "msg": str(exc)}), 500

    @app.route("/api/accounts")
    def api_accounts():
        """从 Java 拉取指定租户的 Temu 卖家账号列表（兼容旧接口），并与本地 session 状态合并。"""
        tenant_id = request.args.get("tenant_id", "")
        accs = _fetch_accounts(java_client, tenant_id or None)
        _state.set_accounts(accs)
        return jsonify({"accounts": accs})

    @app.route("/api/login", methods=["POST"])
    def api_login():
        body = request.get_json(silent=True) or {}
        session_key = (body.get("session_key") or "").strip()
        platform_account_id = (body.get("platform_account_id") or "").strip()
        account = (body.get("account") or "").strip()
        tenant_id_raw = body.get("tenant_id")
        try:
            tenant_id = int(tenant_id_raw) if tenant_id_raw else 0
        except (TypeError, ValueError):
            tenant_id = 0
        if not tenant_id:
            return jsonify({"ok": False, "msg": "缺少 tenant_id"}), 400
        if not session_key and not platform_account_id and not account:
            return jsonify({"ok": False, "msg": "缺少账号信息"}), 400

        from app.session_scope import build_session_key
        if not session_key:
            session_key = build_session_key(account, platform_account_id)

        key_id = session_key or platform_account_id
        with _state.lock:
            _state.logging_in.add(key_id)

        platform = (body.get("platform") or "temu").strip().lower()

        def _do_login():
            try:
                if platform in ("temu", ""):
                    try:
                        from app.browser.profile_sync import pull_profile_if_needed

                        pull_profile_if_needed(
                            java_client,
                            platform="temu",
                            tenant_id=tenant_id,
                            session_key=session_key,
                        )
                    except Exception:
                        pass
                    from agent.temu_tasks import open_login_window, wait_login_session_ready

                    open_login_window(tenant_id, session_key=session_key)
                    # Persist Cookie vault for HTTP sync after user finishes login.
                    try:
                        wait_login_session_ready(
                            tenant_id,
                            session_key=session_key,
                            timeout_seconds=600,
                            poll_seconds=5.0,
                        )
                    except Exception as wait_exc:  # noqa: BLE001
                        print(f"[Panel] temu login wait end: {wait_exc}", file=sys.stderr)
                elif platform == "aliexpress":
                    from agent.aliexpress_tasks import open_login_window
                    open_login_window(tenant_id, session_key=session_key)
                elif platform == "amazon":
                    print(
                        "[Panel] Amazon 账号隔离走紫鸟 browser_id/oauth，请在紫鸟客户端登录对应店铺浏览器。",
                        file=sys.stderr,
                    )
                else:
                    print(f"[Panel] 平台 {platform} 暂不支持本地登录窗口", file=sys.stderr)
            except Exception as exc:
                print(f"[Panel] login error: {exc}", file=sys.stderr)
            finally:
                with _state.lock:
                    _state.logging_in.discard(key_id)

        threading.Thread(target=_do_login, daemon=True).start()
        if platform == "amazon":
            return jsonify({"ok": True, "msg": "Amazon 请在紫鸟客户端登录对应店铺浏览器（已按店隔离）"})
        return jsonify({"ok": True, "msg": "正在打开登录窗口..."})

    @app.route("/api/sync", methods=["POST"])
    def api_sync():
        body = request.get_json(silent=True) or {}
        platform = (body.get("platform") or "temu").strip().lower()
        session_key = (body.get("session_key") or "").strip()
        platform_account_id = (body.get("platform_account_id") or "").strip()
        account = (body.get("account") or "").strip()
        tenant_id_raw = body.get("tenant_id")
        try:
            tenant_id = int(tenant_id_raw) if tenant_id_raw else 0
        except (TypeError, ValueError):
            tenant_id = 0
        if not tenant_id:
            return jsonify({"ok": False, "msg": "缺少 tenant_id"}), 400

        sync_id = session_key or platform_account_id or "__all__"
        with _state.lock:
            _state.syncing.add(sync_id)

        if platform == "amazon":
            try:
                import httpx
                payload = {
                    "scope": "account_health",
                    "platform_account_id": platform_account_id or None,
                    "force": True,
                    "record_cooldown": True,
                }
                endpoint = f"{_api_base()}/api/agent/amazon/sync"
                print(
                    f"[Panel][Amazon] enqueue begin tenant={tenant_id} account={account or '-'} "
                    f"platform_account_id={platform_account_id or '-'} endpoint={endpoint}",
                    file=sys.stderr,
                )
                resp = httpx.post(
                    endpoint,
                    headers={**_api_headers(), "Content-Type": "application/json"},
                    json=payload,
                    timeout=30,
                )
                data = resp.json() if resp.content else {}
                if resp.status_code >= 400:
                    msg = data.get("msg") or data.get("message") or f"HTTP {resp.status_code}"
                    print(
                        f"[Panel][Amazon] enqueue failed status={resp.status_code} msg={msg}",
                        file=sys.stderr,
                    )
                    with _state.lock:
                        _state.last_error = f"Amazon enqueue failed: {msg}"
                    return jsonify({"ok": False, "msg": f"Amazon 入队失败: {msg}"}), resp.status_code
                jobs = (data.get("data") or {}).get("jobs") or data.get("jobs") or []
                job_id = ""
                task_id = ""
                if jobs and isinstance(jobs[0], dict):
                    job_id = str(jobs[0].get("job_id") or "")
                    task_id = str(jobs[0].get("agent_task_id") or "")
                print(
                    f"[Panel][Amazon] enqueue ok tenant={tenant_id} job_id={job_id or '-'} task_id={task_id or '-'}",
                    file=sys.stderr,
                )
                with _state.lock:
                    _state.last_task = f"amazon_sync:{task_id or job_id or 'queued'}"
                return jsonify({
                    "ok": True,
                    "msg": "Amazon 同步任务已入队（将由 Agent 执行）",
                    "job_id": job_id,
                    "task_id": task_id,
                })
            except Exception as exc:
                print(f"[Panel][Amazon] enqueue exception: {exc}", file=sys.stderr)
                with _state.lock:
                    _state.last_error = f"Amazon enqueue exception: {exc}"
                return jsonify({"ok": False, "msg": f"Amazon 入队异常: {exc}"}), 500
            finally:
                with _state.lock:
                    _state.syncing.discard(sync_id)

        def _do_sync():
            try:
                try:
                    from app.browser.profile_sync import pull_profile_if_needed
                    from app.session_scope import build_session_key

                    if session_key or platform_account_id or account:
                        sk = build_session_key(account or session_key, platform_account_id)
                        pull_profile_if_needed(
                            java_client,
                            platform="temu",
                            tenant_id=tenant_id,
                            session_key=sk,
                        )
                except Exception:
                    pass
                from agent.temu_tasks import crawl_and_ingest
                from app.session_scope import build_session_key
                sessions = None
                if session_key or platform_account_id or account:
                    sk = build_session_key(account or session_key, platform_account_id)
                    sessions = [{"session_key": sk, "platform_account_id": platform_account_id, "account": account}]
                crawl_and_ingest(java_client, tenant_id, None, seller_sessions=sessions)
                with _state.lock:
                    _state.last_sync_at = datetime.now().strftime("%H:%M:%S")
                try:
                    from agent.notify import build_success_notification, notify_desktop_deduped

                    title, body = build_success_notification(platform="temu")
                    notify_desktop_deduped(title, body)
                except Exception:
                    pass
            except Exception as exc:
                print(f"[Panel] sync error: {exc}", file=sys.stderr)
                try:
                    from agent.notify import build_reauth_notification, is_reauth_failure, notify_desktop_deduped

                    msg = str(exc)
                    if is_reauth_failure("CRAWL_NOT_LOGGED_IN" if ("未登录" in msg or "登录" in msg) else "", msg):
                        title, body = build_reauth_notification(platform="temu", detail=msg)
                        notify_desktop_deduped(title, body)
                except Exception:
                    pass
            finally:
                with _state.lock:
                    _state.syncing.discard(sync_id)

        threading.Thread(target=_do_sync, daemon=True).start()
        if platform == "amazon":
            return jsonify({"ok": True, "msg": "Amazon 同步任务已入队（将由 Agent 执行）"})
        return jsonify({"ok": True, "msg": "同步任务已启动"})

    @app.route("/api/probe", methods=["POST"])
    def api_probe():
        """主动探测所有账号 session 状态并更新。"""
        body = request.get_json(silent=True) or {}
        tenant_id = str(body.get("tenant_id") or "").strip()

        def _do_probe():
            accs = _fetch_accounts(java_client, tenant_id or None)
            _state.set_accounts(accs)
        threading.Thread(target=_do_probe, daemon=True).start()
        return jsonify({"ok": True})

    return app


def _api_headers() -> dict[str, str]:
    from agent.config import AGENT_TOKEN
    token = (AGENT_TOKEN or os.environ.get("AGENT_TOKEN") or "").strip()
    return {"X-Agent-Token": token}


def _api_base() -> str:
    from agent.config import JAVA_API_URL
    return (JAVA_API_URL or os.environ.get("JAVA_API_URL") or "https://www.yoto.work").rstrip("/")


def _fetch_tenants() -> list[dict]:
    try:
        import httpx
        resp = httpx.get(f"{_api_base()}/api/agent/tenants", headers=_api_headers(), timeout=10)
        data = resp.json() if resp.status_code == 200 else {}
        return data.get("data") or []
    except Exception as exc:
        print(f"[Panel] fetch tenants error: {exc}", file=sys.stderr)
        return []


def _fetch_platform_accounts(tenant_id: str) -> dict[str, list[dict]]:
    try:
        import httpx
        resp = httpx.get(
            f"{_api_base()}/api/agent/platform-accounts",
            params={"tenant_id": tenant_id},
            headers=_api_headers(), timeout=10,
        )
        data = resp.json() if resp.status_code == 200 else {}
        return data.get("data") or {}
    except Exception as exc:
        print(f"[Panel] fetch platform-accounts error: {exc}", file=sys.stderr)
        return {}


def _fetch_ops_messages(tenant_id: int) -> tuple[list[dict[str, Any]], int]:
    """Fetch unified ops (Amazon + Temu + AliExpress) from Java; fallback Amazon-only local."""
    try:
        import httpx

        resp = httpx.get(
            f"{_api_base()}/api/agent/ops/jobs",
            params={"tenant_id": tenant_id},
            headers=_api_headers(),
            timeout=12,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200:
            payload = data.get("data") if isinstance(data, dict) else None
            if isinstance(payload, dict):
                items = payload.get("items")
                if isinstance(items, list):
                    if "unread" in payload:
                        unread = _to_int(payload.get("unread"), 0)
                    else:
                        unread = sum(
                            1
                            for it in items
                            if isinstance(it, dict)
                            and str(it.get("status") or "").lower() == "failed"
                            and it.get("retry_exhausted")
                        )
                    return items, unread
    except Exception as exc:
        print(f"[Panel] fetch ops messages via api error: {exc}", file=sys.stderr)

    amazon_items = _fetch_amazon_ops_messages_fallback(tenant_id)
    unread = sum(
        1
        for it in amazon_items
        if str(it.get("status") or "").lower() == "failed" and it.get("retry_exhausted")
    )
    return amazon_items, unread


def _fetch_amazon_ops_messages_fallback(tenant_id: int) -> list[dict[str, Any]]:
    try:
        import httpx

        resp = httpx.get(
            f"{_api_base()}/api/agent/amazon/sync-jobs",
            params={"tenant_id": tenant_id},
            headers=_api_headers(),
            timeout=10,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200:
            payload = data.get("data") if isinstance(data, dict) else None
            if isinstance(payload, dict):
                items = payload.get("items")
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict):
                            it.setdefault("platform", "amazon")
                            it.setdefault("task_type", "amazon_sync")
                            it.setdefault("title", "Amazon 同步")
                    return items
    except Exception as exc:
        print(f"[Panel] fetch amazon ops messages via api error: {exc}", file=sys.stderr)

    try:
        from app.db import connect

        with connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  j.id,
                  j.platform_account_id,
                  j.agent_task_id,
                  j.scope,
                  j.status,
                  j.error_code,
                  j.error_message,
                  j.result_summary,
                  j.created_at,
                  j.started_at,
                  j.finished_at,
                  COALESCE(pa.store_name, '') AS store_name,
                  COALESCE(pa.account, '') AS account
                FROM amazon_sync_job j
                LEFT JOIN platform_account pa
                  ON pa.id = j.platform_account_id
                 AND pa.tenant_id = j.tenant_id
                WHERE j.tenant_id = ?
                ORDER BY j.created_at DESC
                LIMIT 60
                """,
                (tenant_id,),
            ).fetchall()
    except Exception as exc:
        print(f"[Panel] fetch amazon ops messages local fallback error: {exc}", file=sys.stderr)
        return []

    items: list[dict[str, Any]] = []
    for row in rows:
        summary_text = row["result_summary"] or ""
        summary: dict[str, Any] = {}
        if summary_text:
            try:
                parsed = json.loads(summary_text)
                if isinstance(parsed, dict):
                    summary = parsed
            except Exception:
                summary = {}

        retry_count = _to_int(summary.get("retry_count"), 0)
        max_retry = _to_int(summary.get("max_retry_count"), 2)
        retry_exhausted = bool(summary.get("retry_exhausted"))
        failed_at = summary.get("last_failed_at") or row["finished_at"] or row["started_at"] or row["created_at"] or ""
        failure_reason = summary.get("last_error_message") or row["error_message"] or ""
        failure_code = summary.get("last_error_code") or row["error_code"] or ""

        items.append(
            {
                "platform": "amazon",
                "task_type": "amazon_sync",
                "title": "Amazon 同步",
                "job_id": row["id"],
                "platform_account_id": row["platform_account_id"],
                "agent_task_id": row["agent_task_id"],
                "scope": row["scope"],
                "status": row["status"],
                "store_name": row["store_name"],
                "account": row["account"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "retry_count": retry_count,
                "max_retry_count": max_retry,
                "retry_exhausted": retry_exhausted,
                "failure_code": failure_code,
                "failure_reason": failure_reason,
                "failed_at": failed_at,
                "progress": "已失败，见原因" if str(row["status"] or "").lower() == "failed" else "",
            }
        )
    return items


def _to_int(value: Any, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return fallback
    return fallback


def _fetch_accounts(java_client: Any, tenant_id: str | None = None) -> list[dict]:
    """从 Java API 拉取 Temu seller sessions，合并本地 profile 存在性。"""
    try:
        import httpx
        params = {}
        if tenant_id:
            params["tenant_id"] = tenant_id
        resp = httpx.get(
            f"{_api_base()}/api/agent/temu/seller-sessions",
            headers=_api_headers(), params=params, timeout=10,
        )
        data = resp.json() if resp.status_code == 200 else {}
        sessions: list[dict] = data.get("data") or data.get("sessions") or []
    except Exception as exc:
        print(f"[Panel] fetch accounts error: {exc}", file=sys.stderr)
        sessions = []

    enriched = []
    for s in sessions:
        sk = s.get("session_key") or "default"
        tid = s.get("tenant_id") or int(os.environ.get("AGENT_TENANT_ID", "0"))
        profile_exists = False
        try:
            from app.config import resolve_profile_dir
            p = resolve_profile_dir(tid, sk) if tid else None
            profile_exists = bool(p and p.is_dir())
        except Exception:
            pass

        cache: dict = {}
        try:
            from app.browser.profile_lock import read_session_cache
            if tid:
                cache = read_session_cache(tid, sk) or {}
        except Exception:
            pass

        enriched.append({
            **s,
            "profile_exists": profile_exists,
            "session_ready": cache.get("ready", False),
            "session_checked_at": cache.get("checked_at", ""),
            "cookie_seller": cache.get("seller", "") or cache.get("login_name", ""),
        })

    return enriched


# ─── 托盘图标 ─────────────────────────────────────────────────────────────────
def _make_tray_icon() -> "Image.Image":
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 绿色圆形背景
    d.ellipse([4, 4, size - 4, size - 4], fill=(16, 185, 129, 255))
    # 白色 "C" 字样（简单十字代替）
    m = size // 2
    d.rectangle([m - 12, m - 4, m + 12, m + 4], fill="white")
    d.rectangle([m - 4, m - 12, m + 4, m + 12], fill="white")
    return img


def _open_panel(_icon=None, _item=None) -> None:
    webbrowser.open(f"http://127.0.0.1:{PANEL_PORT}")


def start_tray(stop_event: threading.Event) -> None:
    if not _HAS_TRAY:
        print("[Tray] pystray/Pillow 未安装，跳过托盘。")
        return

    def on_quit(_icon, _item):
        stop_event.set()
        _icon.stop()

    icon = pystray.Icon(
        "crosshub-helper",
        _make_tray_icon(),
        "CrossHub Sync Helper",
        menu=pystray.Menu(
            pystray.MenuItem("打开面板", _open_panel, default=True),
            pystray.MenuItem("退出", on_quit),
        ),
    )
    icon.run_detached()
    print(f"[Tray] 系统托盘已启动，面板: http://127.0.0.1:{PANEL_PORT}")


def start_ops_notify_watcher(stop_event: threading.Event) -> None:
    """Poll Java ops jobs and toast when login-expired Temu/AE failures appear."""

    def _loop() -> None:
        seen: set[str] = set()
        # Skip historical failures on cold start; only notify new ones after first pass.
        primed = False
        while not stop_event.is_set():
            try:
                tenants = _fetch_tenants()
                for t in tenants:
                    if not isinstance(t, dict):
                        continue
                    tid = _to_int(t.get("tenant_id"), 0)
                    if tid <= 0:
                        continue
                    items, _unread = _fetch_ops_messages(tid)
                    if not primed:
                        for it in items:
                            if isinstance(it, dict):
                                jid = str(it.get("id") or it.get("job_id") or "").strip()
                                if jid:
                                    seen.add(f"fail:{jid}")
                                    seen.add(f"ok:{jid}")
                        continue
                    from agent.notify import (
                        build_reauth_notification,
                        build_success_notification,
                        notify_desktop_deduped,
                        ops_error_message,
                        should_notify_ops_item,
                        should_notify_success_ops_item,
                    )

                    for it in items:
                        if should_notify_ops_item(it, seen):
                            plat = str(it.get("platform") or "temu")
                            detail = ops_error_message(it)
                            title, body = build_reauth_notification(platform=plat, detail=detail)
                            notify_desktop_deduped(title, body)
                            print(f"[OpsNotify] tenant={tid} {title}", flush=True)
                        elif should_notify_success_ops_item(it, seen):
                            plat = str(it.get("platform") or "temu")
                            title, body = build_success_notification(
                                platform=plat,
                                shops=it.get("shops_count"),
                                rows=it.get("rows_count"),
                            )
                            notify_desktop_deduped(title, body)
                            print(f"[OpsNotify] tenant={tid} {title}", flush=True)
                primed = True
            except Exception as exc:  # noqa: BLE001
                print(f"[OpsNotify] poll error: {exc}", file=sys.stderr)
            stop_event.wait(45.0)

    threading.Thread(target=_loop, daemon=True, name="ops-notify").start()
    print("[OpsNotify] 运维登录过期通知已启动", flush=True)


# ─── 面板 HTTP 服务 ────────────────────────────────────────────────────────────
def start_panel_server(java_client: Any, stop_event: threading.Event) -> None:
    if not _HAS_FLASK:
        print("[Panel] Flask 未安装，跳过 Web 面板。")
        return

    app = _build_flask_app(java_client)
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    def _run():
        try:
            app.run(host="127.0.0.1", port=PANEL_PORT, debug=False, use_reloader=False)
        except Exception as exc:
            print(f"[Panel] 启动失败: {exc}", file=sys.stderr)

    t = threading.Thread(target=_run, daemon=True, name="panel-server")
    t.start()
    print(f"[Panel] 面板已启动: http://127.0.0.1:{PANEL_PORT}")


# ─── Agent 包装（带状态上报）─────────────────────────────────────────────────
def run_agent_loop(java_client: Any, stop_event: threading.Event) -> None:
    from concurrent.futures import ThreadPoolExecutor, Future

    from agent.config import AGENT_DISPATCH_WORKERS, HEARTBEAT_INTERVAL_SECONDS, POLL_INTERVAL_SECONDS
    from agent.handlers import dispatch_task
    from agent.main import create_ziniao_client, detect_ziniao_online

    _state.update_agent("running")
    consecutive_errors = 0
    inflight: set[Future] = set()
    ziniao_holder: list[Any] = [create_ziniao_client()]
    print(
        "[Agent] supported tasks: temu_crawl,temu_login_open,temu_session_probe,"
        "aliexpress_crawl,aliexpress_login_open,aliexpress_session_probe,"
        "amazon_sync,amazon_write",
        flush=True,
    )

    def _heartbeat_loop() -> None:
        while not stop_event.is_set():
            try:
                java_client.heartbeat(ziniao_online=detect_ziniao_online(ziniao_holder[0]))
            except Exception as exc:  # noqa: BLE001
                print(f"[Agent] 心跳失败: {exc}", file=sys.stderr)
            stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)

    threading.Thread(target=_heartbeat_loop, daemon=True, name="agent-heartbeat").start()

    with ThreadPoolExecutor(max_workers=AGENT_DISPATCH_WORKERS, thread_name_prefix="agent-task") as pool:
        while not stop_event.is_set():
            try:
                done = {f for f in inflight if f.done()}
                for fut in done:
                    inflight.discard(fut)
                    try:
                        fut.result()
                    except Exception as exc:  # noqa: BLE001
                        print(f"[Agent] 任务失败: {exc}", file=sys.stderr)
                tasks = java_client.poll_tasks()
                consecutive_errors = 0
                # 恢复 running 时显式清空 last_error，避免开机连不上的残留一直显示
                _state.update_agent("running", error="")
                for task in tasks:
                    t_type = str(task.get("task_type") or "")
                    _state.update_agent("running", task=t_type)
                    print(f"[Agent] 并行执行: {t_type} ({task.get('task_id')})")
                    fut = pool.submit(dispatch_task, java_client, task)
                    inflight.add(fut)
                    fut.add_done_callback(lambda f: inflight.discard(f))
            except Exception as exc:
                consecutive_errors += 1
                print(f"[Agent] 轮询异常({consecutive_errors}): {exc}", file=sys.stderr)
                if consecutive_errors >= 3:
                    _state.update_agent("error", error=str(exc))

            stop_event.wait(POLL_INTERVAL_SECONDS)

    _state.update_agent("stopped")
