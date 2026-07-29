"""Unit tests for Temu agentseller sales-page navigation guards."""
from __future__ import annotations

import unittest

from app.crawler.temu_nav import (
    is_region_no_permission,
    looks_like_sales_management,
)


class TemuNavTests(unittest.TestCase):
    def test_detect_region_no_permission(self):
        text = "销售管理\n首页\n该区暂无权限"
        self.assertTrue(is_region_no_permission(text))
        self.assertFalse(
            looks_like_sales_management(
                url="https://agentseller.temu.com/mmsos/sales-stock-management/sales-management",
                text=text,
            )
        )

    def test_fully_managed_sales_page_ok(self):
        text = "销售管理全球\nSKU\n建议备货\n今日\n近7天"
        self.assertTrue(
            looks_like_sales_management(
                url="https://agentseller.temu.com/stock/fully-mgt/sale-manage/main",
                text=text,
            )
        )


if __name__ == "__main__":
    unittest.main()
