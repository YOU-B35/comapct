"""Consume website bind codes and persist Helper enrollment to config.json."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from agent.machine_id import machine_fingerprint

DEFAULT_JAVA_API_URL = "https://www.yoto.work"
DEFAULT_DISPLAY_NAME = "本机助手"

_BIND_CLEAR_KEYS = (
    "agent_token",
    "token",
    "user_id",
    "tenant_id",
    "agent_tenant_id",
    "bound_account",
    "bound_user_id",
    "machine_fingerprint",
    "display_name",
)


def default_config_path() -> Path:
    """Same location as sync_helper_app.app_dir()/config.json (load + bind write).

    Prefer Helper app_dir config.json (repo root in dev, exe dir when frozen).
    Fall back to %LOCALAPPDATA%\\CrossHub\\SyncHelper\\config.json only if needed.
    """
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent / "config.json"
    except Exception:
        pass
    # Prefer live sync_helper_app.app_dir() when the Helper process has it on path.
    try:
        import sync_helper_app as sha

        return sha.app_dir() / "config.json"
    except Exception:
        pass
    # Dev fallback: agent/bind.py → repo root (same as scripts/sync_helper_app.app_dir()).
    try:
        return Path(__file__).resolve().parents[3] / "config.json"
    except Exception:
        pass
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "CrossHub" / "SyncHelper" / "config.json"
    return Path.cwd() / "config.json"


def resolve_config_path(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env = (os.environ.get("CROSSHUB_HELPER_CONFIG") or "").strip()
    if env:
        return Path(env)
    return default_config_path()


def _is_isolation_leaf(name: str) -> bool:
    return bool(name) and (name.startswith("user-") or name.startswith("account-"))


def _strip_isolation_leaf(path: Path) -> Path:
    """Drop a trailing user-* / account-* segment so a new bind can re-nest."""
    if _is_isolation_leaf(path.name):
        return path.parent
    return path


def reset_profile_roots() -> None:
    """Clear sticky isolation leaves from TEMU/AE profile root envs + in-memory snapshots.

    After clear/rebind, the next bound user must not inherit a previous user-* leaf
    that resolve_profile_root would otherwise short-circuit on.
    """
    for env_key in ("TEMU_PROFILE_ROOT", "AE_PROFILE_ROOT"):
        raw = (os.environ.get(env_key) or "").strip()
        if not raw:
            continue
        base = _strip_isolation_leaf(Path(raw))
        os.environ[env_key] = str(base)

    try:
        import app.config as app_config

        app_config.PROFILE_ROOT = app_config.resolve_profile_root()
        app_config.AE_PROFILE_ROOT = app_config.resolve_ae_profile_root()
    except Exception:
        pass


def apply_profile_isolation_env() -> None:
    """Nest TEMU/AE roots under the current bound segment (after reset_profile_roots)."""
    try:
        from app.config import _profile_isolation_segment, resolve_ae_profile_root, resolve_profile_root
    except Exception:
        return

    seg = _profile_isolation_segment()
    if not seg:
        return

    temu = resolve_profile_root()
    ae = resolve_ae_profile_root()
    os.environ["TEMU_PROFILE_ROOT"] = str(temu)
    os.environ["AE_PROFILE_ROOT"] = str(ae)
    try:
        import app.config as app_config

        app_config.PROFILE_ROOT = temu
        app_config.AE_PROFILE_ROOT = ae
    except Exception:
        pass


def _read_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_bound_env(cfg: dict[str, Any] | None = None) -> None:
    """Push bound user/tenant into process env for profile isolation + agent client."""
    data = cfg if isinstance(cfg, dict) else {}
    token = str(data.get("agent_token") or data.get("token") or "").strip()
    if token:
        os.environ["AGENT_TOKEN"] = token
    api = str(data.get("java_api_url") or data.get("api_url") or "").strip().rstrip("/")
    if api:
        os.environ["JAVA_API_URL"] = api
    user_id = data.get("user_id") if data.get("user_id") is not None else data.get("bound_user_id")
    if user_id is not None and str(user_id).strip():
        os.environ["CROSSHUB_BOUND_USER_ID"] = str(user_id).strip()
        os.environ["AGENT_USER_ID"] = str(user_id).strip()
    tenant_id = data.get("tenant_id") if data.get("tenant_id") is not None else data.get("agent_tenant_id")
    if tenant_id is not None and str(tenant_id).strip().isdigit():
        os.environ["AGENT_TENANT_ID"] = str(tenant_id).strip()
    bound_account = str(data.get("bound_account") or "").strip()
    if bound_account:
        os.environ["CROSSHUB_BOUND_ACCOUNT"] = bound_account


def consume_bind_code(
    code: str,
    *,
    display_name: str = "",
    config_path: Path | str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """POST /api/agent/bind with snake_case body; persist agent_token (+ related) to config.json."""
    cleaned = (code or "").strip()
    if not cleaned:
        raise ValueError("请输入绑定码")

    fingerprint = machine_fingerprint()
    if not fingerprint:
        raise ValueError("无法生成机器指纹")

    name = (display_name or "").strip() or DEFAULT_DISPLAY_NAME
    api = (base_url or os.environ.get("JAVA_API_URL") or DEFAULT_JAVA_API_URL).strip().rstrip("/")
    if not api:
        api = DEFAULT_JAVA_API_URL

    body = {
        "code": cleaned,
        "machine_fingerprint": fingerprint,
        "display_name": name,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{api}/api/agent/bind", json=body)
        payload = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            msg = (
                (payload.get("msg") if isinstance(payload, dict) else None)
                or (payload.get("message") if isinstance(payload, dict) else None)
                or (payload.get("error") if isinstance(payload, dict) else None)
                or f"HTTP {resp.status_code}"
            )
            raise RuntimeError(str(msg))
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            data = {}
        token = str(data.get("agent_token") or "").strip()
        if not token:
            raise RuntimeError("绑定失败：服务端未返回 agent_token")

    path = resolve_config_path(config_path)
    cfg = _read_config(path)
    cfg["agent_token"] = token
    # Persist the API base that actually accepted this bind.
    # Local Java may still return prod java_api_url in the payload; rewriting
    # would send the new token to online and break local联调.
    cfg["java_api_url"] = api
    if data.get("tenant_id") is not None:
        cfg["tenant_id"] = data.get("tenant_id")
        cfg["agent_tenant_id"] = data.get("tenant_id")
    if data.get("user_id") is not None:
        cfg["user_id"] = data.get("user_id")
        cfg["bound_user_id"] = data.get("user_id")
    cfg["machine_fingerprint"] = fingerprint
    cfg["display_name"] = name
    _write_config(path, cfg)
    # Drop any previous user-* leaf before applying the new bound segment.
    reset_profile_roots()
    apply_bound_env(cfg)
    apply_profile_isolation_env()

    # Hot-reload agent.config module snapshots when already imported.
    try:
        import agent.config as agent_config

        agent_config.AGENT_TOKEN = token
        agent_config.JAVA_API_URL = cfg["java_api_url"]
    except Exception:
        pass

    return {
        "agent_token": token,
        "java_api_url": cfg["java_api_url"],
        "tenant_id": cfg.get("tenant_id"),
        "user_id": cfg.get("user_id"),
        "machine_fingerprint": fingerprint,
        "display_name": name,
        "config_path": str(path),
    }


def clear_binding(config_path: Path | str | None = None) -> dict[str, Any]:
    """Clear enrollment so another CrossHub account can re-bind on the same PC."""
    path = resolve_config_path(config_path)
    cfg = _read_config(path)
    for key in _BIND_CLEAR_KEYS:
        cfg.pop(key, None)
    _write_config(path, cfg)

    for env_key in (
        "AGENT_TOKEN",
        "AGENT_USER_ID",
        "AGENT_TENANT_ID",
        "CROSSHUB_BOUND_USER_ID",
        "CROSSHUB_BOUND_ACCOUNT",
    ):
        os.environ.pop(env_key, None)

    reset_profile_roots()

    try:
        import agent.config as agent_config

        agent_config.AGENT_TOKEN = ""
    except Exception:
        pass

    return {"ok": True, "config_path": str(path)}


def binding_status(config_path: Path | str | None = None) -> dict[str, Any]:
    path = resolve_config_path(config_path)
    cfg = _read_config(path)
    token = str(cfg.get("agent_token") or cfg.get("token") or os.environ.get("AGENT_TOKEN") or "").strip()
    user_id = cfg.get("user_id") if cfg.get("user_id") is not None else cfg.get("bound_user_id")
    return {
        "bound": bool(token),
        "user_id": user_id,
        "tenant_id": cfg.get("tenant_id") or cfg.get("agent_tenant_id"),
        "display_name": cfg.get("display_name") or "",
        "java_api_url": cfg.get("java_api_url") or DEFAULT_JAVA_API_URL,
        "machine_fingerprint": cfg.get("machine_fingerprint") or "",
        "config_path": str(path),
    }
