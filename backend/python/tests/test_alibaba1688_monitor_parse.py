import unittest
from pathlib import Path

from app.platforms.alibaba1688_monitor_parse import (
    parse_offer_detail_responses,
    parse_shop_list_response,
    parse_shopcard_response,
)

FIXTURES = Path(__file__).parent / "fixtures" / "alibaba1688_monitor"


class Alibaba1688MonitorParseTest(unittest.TestCase):
    def _load(self, name):
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_parse_shop_list_tradenumdown(self):
        result = parse_shop_list_response(self._load("moduledata_4.json"))
        self.assertGreaterEqual(len(result["offers"]), 10)
        first = result["offers"][0]
        self.assertEqual(first["offer_id"], "824828511612")
        self.assertEqual(first["rank"], 1)
        self.assertEqual(first["total_sales"], 100000)  # vagueSaleQuantity "10万+"
        self.assertTrue(first["listed_at"])
        self.assertTrue(first["url"].startswith("https://"))

    def test_parse_shop_list_skips_non_tradenumdown(self):
        result = parse_shop_list_response(self._load("moduledata_3.json"))
        self.assertEqual(result["offers"], [])  # wangpu_score list is not the bestseller source
        self.assertEqual(result["member_id"], "b2b-221111714406302508")

    def test_parse_shopcard(self):
        shop = parse_shopcard_response(self._load("shopcard_5.json"))
        self.assertEqual(shop["shop_name"], "深圳市东博瑞户外用品有限公司")
        self.assertEqual(shop["shop_fans"], 722)
        self.assertEqual(shop["shop_return_rate"], "73%")
        self.assertEqual(shop["category"], "垂钓用品")

    def test_parse_offer_detail(self):
        detail = parse_offer_detail_responses(
            [self._load("mmga_9.json"), self._load("mmga_17.json")]
        )
        self.assertIsNotNone(detail["current"])
        self.assertEqual(detail["current"]["offerId"], 930671411701)
        advise = {str(x.get("key")): str(x.get("value")) for x in (detail["advise"] or [])}
        self.assertIn("orderCnt30d", advise)
        self.assertIn("dfPoint", advise)
