"""wait_login_session_ready polls the open login browser and reports ready session."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.temu_tasks import wait_login_session_ready


def test_wait_login_session_ready_writes_cache_and_reports(tmp_path, monkeypatch):
    page = MagicMock()
    runtime = MagicMock()
    runtime.context = MagicMock()
    client = MagicMock()

    status_ready = {
        "url": "https://agentseller.temu.com/",
        "title": "ok",
        "requires_auth": False,
        "logged_in": True,
        "mall_id": "m1",
        "mall_count": 1,
        "malls": [{"mallId": "m1", "mallName": "店"}],
        "ready_hint": True,
    }

    def fake_wait(page_arg, *, tenant_id, timeout_seconds, poll_interval_seconds, on_poll=None, sleeper=None):
        if on_poll:
            on_poll(status_ready)
        return "m1"

    with patch("agent.temu_tasks.get_or_create_temu_runtime", return_value=runtime), \
            patch("agent.temu_tasks.ensure_seller_login_page", return_value=page), \
            patch("app.browser.context.wait_for_login_and_mall", side_effect=fake_wait), \
            patch("app.browser.context.describe_session", return_value=status_ready), \
            patch("agent.temu_tasks.close_tenant_profile_browsers") as close_browsers, \
            patch("app.browser.profile_lock.write_session_cache") as write_cache, \
            patch("app.browser.profile_lock.clear_profile_lock"), \
            patch("app.browser.runtime.discard_browser_runtime", return_value=runtime) as discard_rt, \
            patch("app.browser.temu_cookie_trust.temu_login_cookies_alive", return_value=True), \
            patch("app.browser.profile_sync.push_profile_sync") as push_profile:
        result = wait_login_session_ready(
            5,
            session_key="18061740604",
            timeout_seconds=30,
            poll_seconds=1,
            client=client,
        )

    assert result["ready"] is True
    assert result["session_key"] == "18061740604"
    assert result["mall_id"] == "m1"
    assert write_cache.called
    assert client.report_temu_session.called
    # Owner-thread close: page.context.close + discard registry + soft OS reclaim.
    assert page.context.close.called
    assert discard_rt.called
    assert close_browsers.called
    assert push_profile.called
