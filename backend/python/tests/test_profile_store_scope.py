"""Per-store browser profile isolation for Douyin / 1688 (aligned with Temu)."""
from __future__ import annotations

from pathlib import Path

from agent import douyin_tasks
from app.browser import alibaba1688_context


def test_douyin_profile_dir_scopes_by_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(douyin_tasks, "ROOT", tmp_path)
    default_path = douyin_tasks.profile_dir(5, "default")
    store_path = douyin_tasks.profile_dir(5, "store-abc")
    assert default_path.name == "tenant-5"
    assert store_path == tmp_path / ".douyin-browser-profile" / "tenant-5" / "account-store-abc"
    assert store_path.is_dir()


def test_douyin_profile_dir_prefers_existing_account_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(douyin_tasks, "ROOT", tmp_path)
    nested = tmp_path / ".douyin-browser-profile" / "tenant-5" / "account-store-abc"
    nested.mkdir(parents=True)
    assert douyin_tasks.profile_dir(5, "store-abc") == nested


def test_alibaba1688_profile_dir_scopes_by_store(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / ".1688-browser-profile"
    root.mkdir(parents=True)
    monkeypatch.setattr(
        alibaba1688_context,
        "_PROFILE_ROOT",
        root,
    )
    from app.browser import alibaba1688_context as ctx

    default_path = alibaba1688_context.profile_dir(5, "default")
    store_path = alibaba1688_context.profile_dir(5, "store-xyz")
    assert default_path.name == "tenant-5"
    assert store_path == root / "tenant-5" / "account-store-xyz"
