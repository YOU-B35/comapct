"""跨平台卖家会话作用域：同一租户下按登录账号隔离 Browser Profile。

路径约定：
  {platform}-browser-profile/tenant-{id}/account-{session_key}

- Temu / AliExpress：本地 Playwright Persistent Profile
- Amazon：紫鸟按 browser_id / oauth 隔离（无本地 Profile 目录），session_key 仅作统一标识
"""
from __future__ import annotations

import re
from pathlib import Path

DEFAULT_SESSION_KEY = "default"
_MAX_KEY_LEN = 48

# 平台 → 本地 Profile 根目录环境变量名
_PLATFORM_PROFILE_ENV = {
    "temu": "TEMU_PROFILE_ROOT",
    "aliexpress": "AE_PROFILE_ROOT",
    "douyin": "DOUYIN_PROFILE_ROOT",
    "1688": "A1688_PROFILE_ROOT",
    "alibaba1688": "A1688_PROFILE_ROOT",
}


def normalize_account(account: str) -> str:
    return (account or "").strip().lower()


def build_session_key(account: str, platform_account_id: str = "") -> str:
    """按登录账号生成 session_key；账号为空时回退 platform_account_id。"""
    normalized = normalize_account(account)
    if normalized:
        slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
        if len(slug) > _MAX_KEY_LEN:
            slug = slug[:_MAX_KEY_LEN].rstrip("_")
        if slug:
            return slug
    pa_id = (platform_account_id or "").strip()
    if pa_id:
        return f"pa_{pa_id}"
    return DEFAULT_SESSION_KEY


def normalize_session_key(session_key: str | None) -> str:
    key = (session_key or "").strip()
    return key or DEFAULT_SESSION_KEY


def resolve_platform_profile_dir(
    platform: str,
    tenant_id: int,
    session_key: str | None = None,
    *,
    root: Path | None = None,
) -> Path:
    """解析平台 Profile 目录：tenant-{id}/account-{key}。

    兼容：
    - 旧扁平 tenant-{id}（仅 default 且新目录不存在）
    - 旧 user-*/tenant-{id}/account-{key}（只读回退，新写入仍用无 user 段路径）
    """
    key = normalize_session_key(session_key)
    if root is None:
        raise ValueError("root is required")
    nested = root / f"tenant-{tenant_id}" / f"account-{key}"
    if nested.is_dir():
        return nested
    if key == DEFAULT_SESSION_KEY:
        legacy = root / f"tenant-{tenant_id}"
        if legacy.is_dir():
            return legacy
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name.startswith("user-"):
                candidate = child / f"tenant-{tenant_id}" / f"account-{key}"
                if candidate.is_dir():
                    return candidate
                if key == DEFAULT_SESSION_KEY:
                    flat = child / f"tenant-{tenant_id}"
                    if flat.is_dir():
                        return flat
    return nested


# ── Temu 兼容别名 ──────────────────────────────────────────
build_temu_session_key = build_session_key
normalize_temu_account = normalize_account
