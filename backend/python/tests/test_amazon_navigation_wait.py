from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.amazon.navigation_guard import wait_for_page_patterns


class AmazonNavigationWaitTests(unittest.TestCase):
    def test_returns_as_soon_as_the_target_report_is_rendered(self) -> None:
        page = MagicMock()
        page.url = "https://sellercentral.amazon.com/br"
        page.inner_text.return_value = "DetailSalesTrafficByChild report"

        body = wait_for_page_patterns(
            page,
            (r"DetailSalesTrafficByChild",),
            timeout_seconds=6,
        )

        self.assertIn("DetailSalesTrafficByChild", body)
        page.wait_for_timeout.assert_not_called()

    def test_polls_until_the_target_report_is_rendered(self) -> None:
        page = MagicMock()
        page.url = "https://sellercentral.amazon.com/br"
        page.inner_text.side_effect = ["Loading", "按子商品"]

        body = wait_for_page_patterns(
            page,
            (r"按子商品",),
            timeout_seconds=1,
            poll_seconds=0.1,
        )

        self.assertEqual(body, "按子商品")
        page.wait_for_timeout.assert_called_once_with(100)
