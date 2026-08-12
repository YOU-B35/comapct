import unittest
from unittest.mock import patch

from app.browser import context


class FakePage:
    def __init__(self, urls):
        self.urls = list(urls)
        self.goto_calls = []

    @property
    def url(self):
        return self.urls[0]

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append((url, wait_until, timeout))
        self.urls[0] = url

    def wait_for_load_state(self, state, timeout=None):
        return None

    def bring_to_front(self):
        return None


class LoginWaitTests(unittest.TestCase):
    def test_close_tenant_profile_browsers_targets_only_tenant_profile_processes(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)

            class Result:
                stdout = "2\n"

            return Result()

        with patch.object(context, "resolve_profile_dir", return_value=context.Path(r"D:\app\.temu-browser-profile\tenant-5")), \
                patch.object(context.subprocess, "run", side_effect=fake_run):
            closed = context.close_tenant_profile_browsers(tenant_id=5, sleeper=lambda _: None)

        self.assertEqual(closed, 2)
        script = commands[0][-1]
        self.assertIn("tenant-5", script)
        self.assertIn("account-", script)
        self.assertIn("Stop-Process", script)
        self.assertIn("CommandLine", script)

    def test_wait_for_login_and_mall_keeps_browser_open_until_session_ready(self):
        page = FakePage([
            "https://agentseller.temu.com/auth/authentication",
            "https://agentseller.temu.com/",
        ])
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            page.urls[0] = page.urls[1]

        def fake_requires_auth(url):
            return "authentication" in url

        with patch.object(context, "requires_auth", side_effect=fake_requires_auth), \
                patch.object(context, "resolve_mall_id", return_value="mall-123"):
            mall_id = context.wait_for_login_and_mall(
                page,
                tenant_id=5,
                timeout_seconds=10,
                poll_interval_seconds=1,
                sleeper=fake_sleep,
            )

        self.assertEqual(mall_id, "mall-123")
        self.assertEqual(sleeps, [1])

    def test_wait_for_login_and_mall_times_out_with_tenant_specific_command(self):
        page = FakePage(["https://agentseller.temu.com/auth/authentication"])

        with patch.object(context, "requires_auth", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "Temu 卖家后台尚未登录"):
                context.wait_for_login_and_mall(
                    page,
                    tenant_id=5,
                    timeout_seconds=0,
                    poll_interval_seconds=1,
                    sleeper=lambda _: None,
                )


if __name__ == "__main__":
    unittest.main()
