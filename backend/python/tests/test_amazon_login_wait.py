"""Amazon Seller Central：登录/2FA 等待与有限次刷新重试。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.amazon.session_context import (
    AmazonLoginRequiredError,
    ensure_seller_logged_in_with_wait,
)


class AmazonLoginWaitTests(unittest.TestCase):
    def test_returns_immediately_when_already_logged_in(self):
        page = MagicMock()
        page.url = "https://sellercentral.amazon.com/home"
        body = "账户状况 Account Health 全局快照"

        text = ensure_seller_logged_in_with_wait(
            page,
            body_text=body,
            store_name="Yoto",
            timeout_seconds=30,
            poll_seconds=1,
            max_attempts=3,
            sleeper=lambda _: None,
        )
        self.assertEqual(text, body)
        page.goto.assert_not_called()

    def test_waits_and_succeeds_after_2fa_on_poll(self):
        page = MagicMock()
        page.url = "https://sellercentral.amazon.com/ap/mfa"
        sleeps: list[float] = []

        # attempt1 goto → 2FA；随后 poll 读到已登录
        sequence = [
            "两步验证 请输入一次性密码 OTP 登录",
            "账户状况 全局快照 Seller Central",
        ]
        urls = [
            "https://sellercentral.amazon.com/ap/mfa",
            "https://sellercentral.amazon.com/home",
        ]
        idx = {"i": 0}

        def read_body(*_a, **_k):
            i = min(idx["i"], len(sequence) - 1)
            page.url = urls[i]
            text = sequence[i]
            idx["i"] += 1
            return text

        page.inner_text.side_effect = read_body
        page.evaluate.side_effect = Exception("no evaluate")

        text = ensure_seller_logged_in_with_wait(
            page,
            body_text=sequence[0],
            store_name="Yoto",
            timeout_seconds=15,
            poll_seconds=1,
            max_attempts=3,
            sleeper=sleeps.append,
            home_url="https://sellercentral.amazon.com/home",
        )

        self.assertIn("账户状况", text)
        self.assertGreaterEqual(page.goto.call_count, 1)
        self.assertGreaterEqual(len(sleeps), 1)

    def test_raises_after_max_attempts_exhausted(self):
        page = MagicMock()
        page.url = "https://sellercentral.amazon.com/ap/mfa"
        page.inner_text.return_value = "两步验证 请输入 OTP 登录"
        page.evaluate.side_effect = Exception("no evaluate")

        with patch("app.amazon.session_context.save_capture", return_value="cap.png"):
            with self.assertRaises(AmazonLoginRequiredError) as ctx:
                ensure_seller_logged_in_with_wait(
                    page,
                    body_text="两步验证 OTP",
                    store_name="Yoto",
                    timeout_seconds=3,
                    poll_seconds=1,
                    max_attempts=3,
                    sleeper=lambda _: None,
                    home_url="https://sellercentral.amazon.com/home",
                )

        msg = str(ctx.exception)
        self.assertIn("截图", msg)
        self.assertIn("3", msg)
        self.assertEqual(page.goto.call_count, 3)


if __name__ == "__main__":
    unittest.main()
