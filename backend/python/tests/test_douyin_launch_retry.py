"""Douyin persistent Chrome launch retries when the tenant profile is busy."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.browser.douyin_context import (
    clear_douyin_profile_locks,
    close_douyin_profile_browsers,
    is_douyin_profile_busy_error,
    launch_douyin_persistent_context,
)

BUSY_ERROR = RuntimeError(
    "BrowserType.launch_persistent_context: Target page, context or browser has been closed"
)


def test_is_douyin_profile_busy_error_detects_launch_closed():
    assert is_douyin_profile_busy_error(BUSY_ERROR) is True
    assert is_douyin_profile_busy_error(RuntimeError("SingletonLock already in use")) is True
    assert is_douyin_profile_busy_error(RuntimeError("user data directory is already in use")) is True


def test_is_douyin_profile_busy_error_ignores_unrelated():
    assert is_douyin_profile_busy_error(RuntimeError("DY_NOT_LOGGED_IN: 未登录")) is False
    assert is_douyin_profile_busy_error(RuntimeError("timeout 30000ms exceeded")) is False


def test_clear_douyin_profile_locks_removes_singleton_files(tmp_path: Path):
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile", "DevToolsActivePort"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    default = tmp_path / "Default"
    default.mkdir()
    (default / "LOCK").write_text("x", encoding="utf-8")

    clear_douyin_profile_locks(tmp_path)

    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile", "DevToolsActivePort"):
        assert not (tmp_path / name).exists()
    assert not (default / "LOCK").exists()


def test_has_douyin_profile_lock_detects_singleton_and_default_lock(tmp_path: Path):
    from agent.douyin_tasks import _has_douyin_profile_lock

    assert _has_douyin_profile_lock(tmp_path) is False
    (tmp_path / "SingletonLock").write_text("x", encoding="utf-8")
    assert _has_douyin_profile_lock(tmp_path) is True
    (tmp_path / "SingletonLock").unlink()
    default = tmp_path / "Default"
    default.mkdir()
    (default / "LOCK").write_text("x", encoding="utf-8")
    assert _has_douyin_profile_lock(tmp_path) is True


def test_launch_retries_after_profile_busy_then_succeeds(tmp_path: Path):
    attempts = {"n": 0}
    reclaims: list[int] = []

    def fake_launch():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise BUSY_ERROR
        return "context-ok"

    def fake_reclaim():
        reclaims.append(attempts["n"])
        return 1

    context = launch_douyin_persistent_context(
        playwright=None,
        profile_dir=tmp_path,
        launch_kwargs={},
        launch_fn=fake_launch,
        reclaim_fn=fake_reclaim,
        sleeper=lambda _: None,
    )

    assert context == "context-ok"
    assert attempts["n"] == 2
    assert reclaims == [1]


def test_launch_does_not_retry_unrelated_error(tmp_path: Path):
    attempts = {"n": 0}
    reclaims: list[int] = []

    def fake_launch():
        attempts["n"] += 1
        raise RuntimeError("timeout 30000ms exceeded")

    def fake_reclaim():
        reclaims.append(1)
        return 0

    try:
        launch_douyin_persistent_context(
            playwright=None,
            profile_dir=tmp_path,
            launch_kwargs={},
            launch_fn=fake_launch,
            reclaim_fn=fake_reclaim,
            sleeper=lambda _: None,
        )
        raise AssertionError("expected timeout error")
    except RuntimeError as exc:
        assert "timeout" in str(exc)

    assert attempts["n"] == 1
    assert reclaims == []


def test_launch_raises_after_retries_exhausted(tmp_path: Path):
    attempts = {"n": 0}

    def fake_launch():
        attempts["n"] += 1
        raise BUSY_ERROR

    try:
        launch_douyin_persistent_context(
            playwright=None,
            profile_dir=tmp_path,
            launch_kwargs={},
            attempts=3,
            launch_fn=fake_launch,
            reclaim_fn=lambda: 1,
            sleeper=lambda _: None,
        )
        raise AssertionError("expected busy error")
    except RuntimeError as exc:
        assert "has been closed" in str(exc)

    assert attempts["n"] == 3


def test_close_douyin_profile_browsers_targets_douyin_profile(tmp_path: Path):
    commands = []

    class Result:
        stdout = "1\n"

    def fake_run(command, **kwargs):
        commands.append(command)
        return Result()

    profile = tmp_path / ".douyin-browser-profile" / "tenant-5"
    profile.mkdir(parents=True)
    (profile / "SingletonLock").write_text("x", encoding="utf-8")

    with patch("app.browser.douyin_context.subprocess.run", side_effect=fake_run), patch(
        "app.browser.douyin_context.sys.platform", "win32"
    ):
        closed = close_douyin_profile_browsers(profile, sleeper=lambda _: None)

    assert closed == 1
    script = commands[0][-1]
    assert "tenant-5" in script
    assert ".douyin-browser-profile" in script.lower() or "douyin-browser-profile" in script.lower()
    assert "Stop-Process" in script
    assert not (profile / "SingletonLock").exists()


def test_douyin_launch_kwargs_ignore_disable_extensions():
    from agent.douyin_tasks import _douyin_launch_kwargs

    kwargs = _douyin_launch_kwargs(headless=False)
    ignored = kwargs.get("ignore_default_args") or []
    assert "--disable-extensions" in ignored
    assert "--enable-automation" in ignored


def test_launch_starts_fresh_playwright_after_busy_error(tmp_path: Path, monkeypatch):
    from agent import douyin_tasks as dt

    starts = {"n": 0}
    launches = {"n": 0}
    stops = {"n": 0}

    class FakePlaywright:
        def __init__(self):
            self.chromium = self

        def launch_persistent_context(self, *args, **kwargs):
            launches["n"] += 1
            if launches["n"] == 1:
                raise BUSY_ERROR
            return object()

        def stop(self):
            stops["n"] += 1

    class FakeSync:
        def start(self):
            starts["n"] += 1
            return FakePlaywright()

    monkeypatch.setattr(dt, "profile_dir", lambda tenant_id: tmp_path)
    monkeypatch.setattr(dt, "sanitize_profile_startup_for_douyin", lambda *a, **k: None)
    monkeypatch.setattr(dt, "install_douyin_only_tab_guard", lambda ctx: None)
    monkeypatch.setattr(dt, "ensure_douyin_home_page", lambda ctx, force_navigate=True: "page")
    monkeypatch.setattr(dt, "close_douyin_profile_browsers", lambda *a, **k: 1)
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSync())

    pw, context, page = dt._launch(5, headless=False)

    assert page == "page"
    assert context is not None
    assert pw is not None
    assert starts["n"] == 2
    assert launches["n"] == 2
    assert stops["n"] == 1


def test_launch_reclaims_existing_singleton_lock_before_first_attempt(tmp_path: Path, monkeypatch):
    from agent import douyin_tasks as dt

    (tmp_path / "SingletonLock").write_text("held", encoding="utf-8")
    reclaims: list[str] = []
    launches = {"n": 0}

    class FakePlaywright:
        def __init__(self):
            self.chromium = self

        def launch_persistent_context(self, *args, **kwargs):
            launches["n"] += 1
            return object()

        def stop(self):
            pass

    class FakeSync:
        def start(self):
            return FakePlaywright()

    def fake_reclaim(profile_dir, **kwargs):
        reclaims.append(str(profile_dir))
        return 1

    monkeypatch.setattr(dt, "profile_dir", lambda tenant_id: tmp_path)
    monkeypatch.setattr(dt, "sanitize_profile_startup_for_douyin", lambda *a, **k: None)
    monkeypatch.setattr(dt, "install_douyin_only_tab_guard", lambda ctx: None)
    monkeypatch.setattr(dt, "ensure_douyin_home_page", lambda ctx, force_navigate=True: "page")
    monkeypatch.setattr(dt, "close_douyin_profile_browsers", fake_reclaim)
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSync())

    dt._launch(5, headless=False)

    assert reclaims == [str(tmp_path)]
    assert launches["n"] == 1


def test_launch_reclaims_before_sanitize_when_lock_present(tmp_path: Path, monkeypatch):
    from agent import douyin_tasks as dt

    (tmp_path / "SingletonLock").write_text("held", encoding="utf-8")
    order: list[str] = []

    class FakePlaywright:
        def __init__(self):
            self.chromium = self

        def launch_persistent_context(self, *args, **kwargs):
            order.append("launch")
            return object()

        def stop(self):
            pass

    class FakeSync:
        def start(self):
            return FakePlaywright()

    monkeypatch.setattr(dt, "profile_dir", lambda tenant_id: tmp_path)
    monkeypatch.setattr(
        dt,
        "sanitize_profile_startup_for_douyin",
        lambda *a, **k: order.append("sanitize"),
    )
    monkeypatch.setattr(dt, "install_douyin_only_tab_guard", lambda ctx: None)
    monkeypatch.setattr(dt, "ensure_douyin_home_page", lambda ctx, force_navigate=True: "page")
    monkeypatch.setattr(
        dt,
        "close_douyin_profile_browsers",
        lambda *a, **k: order.append("reclaim") or 1,
    )
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSync())

    dt._launch(5, headless=False)

    assert order[:2] == ["reclaim", "sanitize"]
    assert order[-1] == "launch"
