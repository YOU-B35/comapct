"""Sync Helper Java API URL resolution (local vs production).

Production default remains https://www.yoto.work.
Local联调 requires CROSSHUB_ALLOW_LOCAL_JAVA=1 or config.allow_local_java=true.
When allow_local_java is on and config points at :18080, that wins over a stale
parent-shell JAVA_API_URL (common after prod sessions / protocol re-launch).
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_JAVA_API_URL = "https://www.yoto.work"


def allow_local_java(cfg: dict[str, Any] | None = None) -> bool:
    if os.environ.get("CROSSHUB_ALLOW_LOCAL_JAVA", "").strip().lower() in {"1", "true", "yes"}:
        return True
    if isinstance(cfg, dict):
        flag = cfg.get("allow_local_java")
        if flag is True:
            return True
        if str(flag or "").strip().lower() in {"1", "true", "yes"}:
            return True
    return False


def is_local_java_api(url: str) -> bool:
    text = (url or "").strip().lower()
    if not text:
        return False
    host_local = ("127.0.0.1" in text) or ("localhost" in text)
    return host_local and (":18080" in text or text.rstrip("/").endswith("18080"))


def normalize_java_api_url(api: str, cfg: dict[str, Any] | None = None) -> str:
    """Force online when local URL is set without an explicit local-allow flag."""
    cleaned = (api or "").strip().rstrip("/")
    if not cleaned:
        return DEFAULT_JAVA_API_URL
    if is_local_java_api(cleaned) and not allow_local_java(cfg):
        return DEFAULT_JAVA_API_URL
    return cleaned


def resolve_java_api_url(
    cfg: dict[str, Any] | None = None,
    *,
    env_api: str | None = None,
) -> tuple[str, str]:
    """Return (api_url, note). Prefer local config when allow_local_java is set."""
    data = cfg if isinstance(cfg, dict) else {}
    cfg_api = str(data.get("java_api_url") or data.get("api_url") or "").strip().rstrip("/")
    if env_api is None:
        env_val = (os.environ.get("JAVA_API_URL") or "").strip().rstrip("/")
    else:
        env_val = (env_api or "").strip().rstrip("/")

    if allow_local_java(data) and is_local_java_api(cfg_api):
        note = ""
        if env_val and env_val.rstrip("/") != cfg_api:
            note = f"allow_local_java: using config {cfg_api} (ignore env JAVA_API_URL={env_val})"
        return cfg_api, note

    chosen = normalize_java_api_url(env_val or cfg_api or "", data)
    note = ""
    if is_local_java_api(env_val or cfg_api) and chosen == DEFAULT_JAVA_API_URL:
        note = (
            f"java_api_url local blocked → {DEFAULT_JAVA_API_URL}; "
            "set CROSSHUB_ALLOW_LOCAL_JAVA=1 or config allow_local_java=true"
        )
    return chosen, note


def sync_agent_config_module(*, api: str, token: str = "") -> None:
    """Keep agent.config module snapshots aligned with process env after load_config."""
    try:
        import agent.config as agent_config

        agent_config.JAVA_API_URL = (api or DEFAULT_JAVA_API_URL).rstrip("/")
        if token:
            agent_config.AGENT_TOKEN = token.strip()
    except Exception:
        pass
