"""Pull/push browser profile bundles via Java Agent API."""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

from app.browser.profile_bundle import (
    pack_profile_from_live_dir,
    should_pull_remote,
    unpack_profile_bundle,
    write_remote_sha_cache,
)
from app.config import resolve_profile_dir
from app.temu.session_scope import normalize_session_key

logger = logging.getLogger(__name__)


def profile_sync_enabled() -> bool:
    return os.environ.get("CROSSHUB_PROFILE_SYNC", "1").strip().lower() not in ("0", "false", "no")


def profile_push_enabled() -> bool:
    return profile_sync_enabled() and os.environ.get("CROSSHUB_PROFILE_SYNC_PUSH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def profile_pull_enabled() -> bool:
    return profile_sync_enabled() and os.environ.get("CROSSHUB_PROFILE_SYNC_PULL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _close_temu_runtime(tenant_id: int, session_key: str | None) -> None:
    try:
        from app.browser.runtime import close_browser_runtime

        close_browser_runtime(tenant_id=tenant_id, session_key=session_key)
    except Exception:
        pass
    try:
        from app.browser.context import close_tenant_profile_browsers

        close_tenant_profile_browsers(tenant_id, session_key=session_key)
    except Exception:
        pass


def push_profile_sync(
    client: Any,
    *,
    platform: str,
    tenant_id: int,
    session_key: str,
    platform_account_id: str = "",
    account: str = "",
) -> dict[str, Any] | None:
    if not profile_push_enabled():
        return None
    token_tenant = client.resolve_agent_tenant_id()
    if token_tenant is not None and int(token_tenant) != int(tenant_id):
        logger.warning("[ProfileSync] skip push: tenant %s != token tenant %s", tenant_id, token_tenant)
        return None

    key = normalize_session_key(session_key)
    profile_dir = resolve_profile_dir(tenant_id, key)

    def _close() -> None:
        _close_temu_runtime(tenant_id, key)

    bundle, manifest = pack_profile_from_live_dir(
        profile_dir,
        tenant_id=tenant_id,
        platform=platform,
        session_key=key,
        platform_account_id=platform_account_id,
        account=account,
        close_runtime=_close,
    )
    result = client.upload_profile(platform, tenant_id, key, bundle)
    sha = str((result or {}).get("bundle_sha256") or manifest.get("bundle_sha256") or "")
    if sha:
        write_remote_sha_cache(profile_dir, sha)
    logger.info("[ProfileSync] pushed %s tenant=%s session=%s bytes=%s", platform, tenant_id, key, len(bundle))
    return result


def push_profile_async(
    client: Any,
    *,
    platform: str,
    tenant_id: int,
    session_key: str,
    platform_account_id: str = "",
    account: str = "",
) -> None:
    if not profile_push_enabled():
        return

    def _run() -> None:
        try:
            push_profile_sync(
                client,
                platform=platform,
                tenant_id=tenant_id,
                session_key=session_key,
                platform_account_id=platform_account_id,
                account=account,
            )
        except Exception as exc:
            logger.warning("[ProfileSync] async push failed: %s", exc)

    threading.Thread(target=_run, daemon=True, name=f"profile-push-{tenant_id}-{session_key}").start()


def pull_profile_if_needed(
    client: Any,
    *,
    platform: str,
    tenant_id: int,
    session_key: str,
) -> bool:
    if not profile_pull_enabled():
        return False
    token_tenant = client.resolve_agent_tenant_id()
    if token_tenant is not None and int(token_tenant) != int(tenant_id):
        logger.warning("[ProfileSync] skip pull: tenant %s != token tenant %s", tenant_id, token_tenant)
        return False

    key = normalize_session_key(session_key)
    profile_dir = resolve_profile_dir(tenant_id, key)

    status, etag = client.head_profile(platform, tenant_id, key)
    if status == 404:
        return False
    if status == 304:
        return False
    if status != 200 or not etag:
        return False
    if not should_pull_remote(profile_dir, etag):
        return False

    data, remote_etag = client.download_profile(platform, tenant_id, key)
    if not data:
        return False

    _close_temu_runtime(tenant_id, key)
    unpack_profile_bundle(data, profile_dir)
    write_remote_sha_cache(profile_dir, remote_etag or etag)
    logger.info("[ProfileSync] pulled %s tenant=%s session=%s", platform, tenant_id, key)
    return True


def pull_all_for_tenant(client: Any, tenant_id: int) -> None:
    if not profile_pull_enabled():
        return
    token_tenant = client.resolve_agent_tenant_id()
    if token_tenant is None:
        logger.warning("[ProfileSync] skip pull_all: unknown agent tenant")
        return
    if int(token_tenant) != int(tenant_id):
        logger.warning("[ProfileSync] skip pull_all: tenant %s != token tenant %s", tenant_id, token_tenant)
        return

    rows = client.list_profiles("temu", tenant_id)
    if rows:
        for row in rows:
            session_key = str(row.get("session_key") or "").strip()
            if session_key:
                pull_profile_if_needed(client, platform="temu", tenant_id=tenant_id, session_key=session_key)
        return

    try:
        from app.session_scope import build_session_key

        accounts = client.list_platform_accounts(tenant_id).get("temu") or []
        for acc in accounts:
            if not isinstance(acc, dict):
                continue
            session_key = build_session_key(
                str(acc.get("account") or ""),
                str(acc.get("id") or acc.get("platform_account_id") or ""),
            )
            pull_profile_if_needed(client, platform="temu", tenant_id=tenant_id, session_key=session_key)
    except Exception as exc:
        logger.warning("[ProfileSync] pull_all fallback failed: %s", exc)
