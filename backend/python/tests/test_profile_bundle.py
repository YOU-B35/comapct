from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.browser.profile_bundle import (
    REMOTE_SHA_CACHE_KEY,
    pack_profile_essentials,
    read_remote_sha_cache,
    should_pull_remote,
    unpack_profile_bundle,
    write_remote_sha_cache,
)


def _write_cookies(profile_dir: Path) -> None:
    path = profile_dir / "Default" / "Network" / "Cookies"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"sqlite-cookie-data" * 512)


def test_pack_includes_session_cache_and_cookies(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    _write_cookies(profile)
    (profile / ".crosshub-session.json").write_text(
        '{"ready": true, "mall_id": "634"}',
        encoding="utf-8",
    )
    data, manifest = pack_profile_essentials(
        profile,
        tenant_id=5,
        platform="temu",
        session_key="18061740604",
    )
    assert manifest["bundle_sha256"]
    assert data[:2] == b"PK"


def test_unpack_rejects_zip_slip(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../evil.txt", b"bad")
    with pytest.raises(ValueError, match="unsafe zip entry"):
        unpack_profile_bundle(buffer.getvalue(), tmp_path / "out")


def test_should_pull_when_remote_sha_differs(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    write_remote_sha_cache(profile, "aaa")
    assert should_pull_remote(profile, "bbb") is True
    assert should_pull_remote(profile, "aaa") is False


def test_remote_sha_cache_roundtrip(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    write_remote_sha_cache(profile, "deadbeef")
    assert read_remote_sha_cache(profile) == "deadbeef"
    cache = (profile / ".crosshub-session.json").read_text(encoding="utf-8")
    assert REMOTE_SHA_CACHE_KEY in cache
