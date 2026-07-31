"""Pack/unpack essential browser profile files for cloud sync."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REMOTE_SHA_CACHE_KEY = "remote_bundle_sha256"

ESSENTIAL_REL_PATHS: tuple[str, ...] = (
    ".crosshub-session.json",
    "Default/Network/Cookies",
    "Default/Login Data",
    "Default/Preferences",
    "Default/Secure Preferences",
    "Local State",
)

CACHE_FILENAME = ".crosshub-session.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_remote_sha_cache(profile_dir: Path) -> str | None:
    cache = _read_session_cache(profile_dir)
    if not cache:
        return None
    value = str(cache.get(REMOTE_SHA_CACHE_KEY) or "").strip()
    return value or None


def write_remote_sha_cache(profile_dir: Path, sha256: str) -> None:
    cache = _read_session_cache(profile_dir) or {}
    cache[REMOTE_SHA_CACHE_KEY] = sha256
    path = profile_dir / CACHE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def should_pull_remote(profile_dir: Path, remote_sha: str | None) -> bool:
    if not remote_sha:
        return False
    local = read_remote_sha_cache(profile_dir)
    return local != remote_sha


def _read_session_cache(profile_dir: Path) -> dict[str, Any] | None:
    path = profile_dir / CACHE_FILENAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _assert_safe_zip_name(name: str) -> None:
    normalized = _normalize_zip_name(name)
    if ".." in normalized.split("/"):
        raise ValueError(f"unsafe zip entry: {name}")


def pack_profile_essentials(
    profile_dir: Path,
    *,
    tenant_id: int,
    platform: str,
    session_key: str,
    platform_account_id: str = "",
    account: str = "",
    packed_by_agent_id: str = "",
) -> tuple[bytes, dict[str, Any]]:
    profile_dir = profile_dir.resolve()
    if not profile_dir.is_dir():
        raise FileNotFoundError(f"profile dir missing: {profile_dir}")

    files_meta: list[dict[str, str]] = []
    payloads: dict[str, bytes] = {}

    for rel in ESSENTIAL_REL_PATHS:
        src = profile_dir / rel
        if not src.is_file():
            continue
        data = src.read_bytes()
        files_meta.append({"path": rel, "sha256": _sha256_bytes(data)})
        payloads[rel] = data

    if not any(item["path"] == ".crosshub-session.json" for item in files_meta):
        cache = _read_session_cache(profile_dir)
        if cache:
            data = json.dumps(cache, ensure_ascii=False).encode("utf-8")
            files_meta.append({"path": ".crosshub-session.json", "sha256": _sha256_bytes(data)})
            payloads[".crosshub-session.json"] = data

    if not any(item["path"] == "Default/Network/Cookies" for item in files_meta):
        raise FileNotFoundError("Cookies file missing; cannot pack profile")

    manifest: dict[str, Any] = {
        "version": 1,
        "platform": platform,
        "tenant_id": tenant_id,
        "session_key": session_key,
        "platform_account_id": platform_account_id,
        "account": account or session_key,
        "files": files_meta,
        "bundle_sha256": "",
        "bundle_bytes": 0,
        "packed_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "packed_by_agent_id": packed_by_agent_id,
    }

    def build_zip(include_manifest_sha: str) -> bytes:
        body = dict(manifest)
        body["bundle_sha256"] = include_manifest_sha
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel, data in payloads.items():
                zf.writestr(rel, data)
            zf.writestr("manifest.json", json.dumps(body, ensure_ascii=False).encode("utf-8"))
        return buffer.getvalue()

    zip_bytes = build_zip("")
    zip_sha = _sha256_bytes(zip_bytes)
    zip_bytes = build_zip(zip_sha)
    final_sha = _sha256_bytes(zip_bytes)
    if final_sha != zip_sha:
        zip_bytes = build_zip(final_sha)
        final_sha = _sha256_bytes(zip_bytes)

    manifest["bundle_sha256"] = final_sha
    manifest["bundle_bytes"] = len(zip_bytes)
    return zip_bytes, manifest


def unpack_profile_bundle(data: bytes, profile_dir: Path) -> None:
    profile_dir = profile_dir.resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _normalize_zip_name(info.filename)
            _assert_safe_zip_name(name)
            if name == "manifest.json":
                continue
            target = profile_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))


def copy_profile_tree_for_pack(profile_dir: Path) -> Path:
    """Copy profile to temp dir so Chrome locks do not block reads."""
    temp_root = Path(tempfile.mkdtemp(prefix="crosshub-profile-pack-"))
    dest = temp_root / "profile"
    shutil.copytree(profile_dir, dest, dirs_exist_ok=True)
    return dest


def pack_profile_from_live_dir(
    profile_dir: Path,
    *,
    tenant_id: int,
    platform: str,
    session_key: str,
    platform_account_id: str = "",
    account: str = "",
    packed_by_agent_id: str = "",
    close_runtime: Callable[[], None] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    if close_runtime is not None:
        try:
            close_runtime()
        except Exception:
            pass
    temp_copy = copy_profile_tree_for_pack(profile_dir)
    try:
        return pack_profile_essentials(
            temp_copy,
            tenant_id=tenant_id,
            platform=platform,
            session_key=session_key,
            platform_account_id=platform_account_id,
            account=account,
            packed_by_agent_id=packed_by_agent_id,
        )
    finally:
        shutil.rmtree(temp_copy.parent, ignore_errors=True)
