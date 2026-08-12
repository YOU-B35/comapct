from pathlib import Path

import pytest


def test_profile_root_ignores_bound_user_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TEMU_PROFILE_ROOT", str(tmp_path))
    monkeypatch.setenv("CROSSHUB_BOUND_USER_ID", "55")
    from app.config import resolve_profile_root

    assert resolve_profile_root() == tmp_path


def test_resolve_dir_falls_back_to_legacy_user_segment(tmp_path):
    legacy = tmp_path / "user-55" / "tenant-5" / "account-default"
    legacy.mkdir(parents=True)
    from app.session_scope import resolve_platform_profile_dir

    got = resolve_platform_profile_dir("temu", 5, "default", root=tmp_path)
    assert got == legacy


def test_resolve_dir_prefers_new_path_when_present(tmp_path):
    legacy = tmp_path / "user-55" / "tenant-5" / "account-default"
    legacy.mkdir(parents=True)
    modern = tmp_path / "tenant-5" / "account-default"
    modern.mkdir(parents=True)
    from app.session_scope import resolve_platform_profile_dir

    assert resolve_platform_profile_dir("temu", 5, "default", root=tmp_path) == modern
