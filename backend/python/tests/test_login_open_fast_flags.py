"""open_login_window sanitizes profile and launches Temu-only."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.temu_tasks import open_login_window


def test_open_login_window_uses_temu_only_launch_flags():
    fake_page = MagicMock()
    fake_page.url = "https://agentseller.temu.com/"
    fake_runtime = MagicMock()
    fake_runtime.context = object()

    with patch("agent.temu_tasks.browser_runtime.peek_browser_runtime", return_value=None), \
            patch("agent.temu_tasks.get_or_create_temu_runtime", return_value=fake_runtime) as get_runtime, \
            patch("agent.temu_tasks.ensure_seller_login_page", return_value=fake_page), \
            patch("agent.temu_tasks.close_temu_runtime"), \
            patch("agent.temu_tasks.close_tenant_profile_browsers"), \
            patch("app.browser.profile_startup.sanitize_profile_startup_for_temu") as sanitize, \
            patch("agent.temu_tasks.resolve_profile_dir", create=True), \
            patch("app.config.resolve_profile_dir", return_value=MagicMock()):
        open_login_window(tenant_id=5, session_key="18061740604")

    sanitize.assert_called_once()
    get_runtime.assert_called_once_with(
        5,
        headless=False,
        session_key="18061740604",
        skip_profile_pull=True,
        force_kill_browsers=True,
    )
