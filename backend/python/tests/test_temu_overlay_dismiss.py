"""Temu overlay dismiss helpers."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.crawler import temu_nav


class TemuOverlayDismissTests(unittest.TestCase):
    def test_dismiss_js_targets_common_close_actions(self):
        js = temu_nav.DISMISS_TEMU_OVERLAYS_JS
        self.assertIn("role=\"dialog\"", js)
        self.assertIn("知道了", js)
        self.assertIn("我知道了", js)
        self.assertIn("暂不", js)
        self.assertIn("关闭", js)
        self.assertIn("CLOSE_RE", js)

    def test_dismiss_temu_ui_blockers_calls_page_evaluate(self):
        page = MagicMock()
        page.evaluate.return_value = 3
        page.keyboard = MagicMock()
        # default rounds=2：每轮关闭 3 个 → 合计 6；Escape 在 Python 侧按键盘
        closed = temu_nav.dismiss_temu_ui_blockers(page)
        self.assertEqual(closed, 6)
        page.evaluate.assert_called()
        page.keyboard.press.assert_called_with("Escape")

    def test_ensure_sales_page_dismisses_before_navigation(self):
        page = MagicMock()
        page.url = "https://agentseller.temu.com/home"
        page.keyboard = MagicMock()

        def _eval(js, *args, **kwargs):
            text = str(js)
            if "dialog" in text or "知道了" in text:
                return 1
            if "innerText" in text:
                # After goto, url mock flips to sales page
                if "sale-manage" in (page.url or ""):
                    return "销售管理\nSKU\n建议备货\n今日\n近7天"
                return "首页公告"
            return 0

        page.evaluate.side_effect = _eval

        def _goto(url, **kwargs):
            page.url = url

        page.goto.side_effect = _goto

        temu_nav.ensure_fully_managed_sales_page(page)

        page.goto.assert_called()
        first_js = page.evaluate.call_args_list[0].args[0]
        self.assertIn("dialog", first_js)


if __name__ == "__main__":
    unittest.main()
