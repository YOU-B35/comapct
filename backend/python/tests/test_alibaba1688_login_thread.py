"""1688 login/probe must run Playwright on a clean thread (mirror Douyin).

Wiki: Helper tray/flask installs an asyncio loop on the current thread; calling
playwright sync_api from that same thread raises
"Playwright Sync API inside the asyncio loop" (production A1688_LOGIN_FAILED).
"""
from __future__ import annotations

import threading


class _FakePage:
    url = "https://work.1688.com/"
    def goto(self, *a, **k):
        return None
    def wait_for_timeout(self, *a, **k):
        return None


def _fake_pw_context_pair():
    class _Ctx:
        def pages(self):
            return []
        def cookies(self):
            return []
        def close(self):
            return None
    class _Pw:
        def __init__(self):
            self.chromium = self
        def stop(self):
            return None
    return _Pw(), _Ctx(), _FakePage()


def test_probe_session_runs_playwright_on_clean_thread(monkeypatch):
    import agent.alibaba1688_tasks as mod

    seen = {}
    outer = threading.get_ident()

    def fake_launch(tenant_id, *, headless=True, goto=None, store_id=None):
        seen["thread"] = threading.get_ident()
        return _fake_pw_context_pair()

    monkeypatch.setattr(mod, "_launch", fake_launch)
    monkeypatch.setattr(mod, "persist_1688_session", lambda *a, **k: {})
    monkeypatch.setattr(mod, "_looks_logged_in", lambda *a, **k: False)

    result = mod.probe_session(5)
    assert result.get("logged_in") is False
    # Must be a different thread than the caller, otherwise Playwright sees an
    # asyncio loop and raises on login/probe in the helper.
    assert seen["thread"] is not None
    assert seen["thread"] != outer


def test_open_login_window_runs_playwright_on_clean_thread(monkeypatch):
    import agent.alibaba1688_tasks as mod

    seen = {"thread": None}
    outer = threading.get_ident()

    def fake_launch(tenant_id, *, headless=True, goto=None, store_id=None):
        seen["thread"] = threading.get_ident()
        return _fake_pw_context_pair()

    monkeypatch.setattr(mod, "_launch", fake_launch)
    monkeypatch.setattr(mod, "_looks_logged_in", lambda *a, **k: True)
    monkeypatch.setattr(mod, "persist_1688_session", lambda *a, **k: {})
    monkeypatch.setattr(mod, "_close", lambda *a, **k: None)
    monkeypatch.setattr(mod.time, "monotonic", lambda: 1_000_000)

    result = mod.open_login_window(5, timeout_seconds=1)
    assert result.get("logged_in") is True
    assert seen["thread"] not in (None, outer)


def test_browser_refuses_system_chrome_when_bundled_missing(monkeypatch):
    from agent.alibaba1688_tasks import _a1688_launch_kwargs

    monkeypatch.setattr("app.browser.context._bundled_chromium_ready", lambda: False)
    try:
        _a1688_launch_kwargs(headless=False)
    except RuntimeError as exc:
        assert "A1688_BROWSER_UNAVAILABLE" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when bundled chromium is missing")
