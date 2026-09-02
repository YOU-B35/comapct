import unittest
from unittest.mock import MagicMock, patch

from app.crawler.temu_api import TemuApiClient


class TemuApiOptimizationTests(unittest.TestCase):
    def test_switch_mall_does_not_reinitialize_current_mall(self):
        client = object.__new__(TemuApiClient)
        client.mall_id = "mall-1"
        client.page = MagicMock()
        client.ensure_sales_context = MagicMock()

        with patch("app.crawler.temu_api.set_mall_id") as set_mall:
            client.switch_mall("mall-1")

        set_mall.assert_not_called()
        client.ensure_sales_context.assert_not_called()

    def test_switch_mall_reinitializes_after_actual_change(self):
        client = object.__new__(TemuApiClient)
        client.mall_id = "mall-1"
        client.page = MagicMock()
        client.ensure_sales_context = MagicMock()

        with patch("app.crawler.temu_api.set_mall_id") as set_mall:
            client.switch_mall("mall-2")

        set_mall.assert_called_once_with(client.page, "mall-2")
        client.ensure_sales_context.assert_called_once()
        self.assertEqual(client.mall_id, "mall-2")


if __name__ == "__main__":
    unittest.main()
