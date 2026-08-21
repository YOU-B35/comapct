import unittest
from unittest.mock import patch

from app.platforms.alibaba1688_monitor_adapter import Alibaba1688MonitorAdapter


class Alibaba1688MonitorAdapterTest(unittest.TestCase):
    def test_crawl_target_maps_products(self):
        fake_payload = {
            "platform": "1688",
            "snapshot_at": "2026-08-20 10:00:00",
            "products": [
                {
                    "offer_id": "930671411701",
                    "title": "东博瑞 KRANK HOOK",
                    "price": "0.5",
                    "sale_text": "已售10万+件",
                    "total_sales": 100000,
                    "rank": 1,
                    "listed_at": "2024-08-15",
                    "url": "https://detail.1688.com/offer/930671411701.html",
                    "image_url": "https://cbu01.alicdn.com/img/ibank/example.jpg",
                    "shop_name": "深圳市东博瑞户外用品有限公司",
                    "shop_url": "https://shop16yx1905b2433.1688.com",
                    "shop_fans": 722,
                    "quality_rate": "100%",
                    "shop_return_rate": "73%",
                    "dropship_7d": "100以内",
                    "dropship_30d": "100以内",
                    "dropship_heat": 195,
                    "rebuy_rate": "复购率48.1%",
                    "attrs_json": '[{"property":"品牌","value":"东博瑞"}]',
                    "is_pinned": 1,
                    "raw_json": "{}",
                }
            ],
            "shop": {},
            "meta": {"member_id": "b2b-x"},
        }
        with patch(
            "app.platforms.alibaba1688_monitor_adapter.crawl_shop",
            return_value=fake_payload,
        ):
            result = Alibaba1688MonitorAdapter().crawl_target(
                tenant_id=5,
                target={"target_url": "https://shop16yx1905b2433.1688.com"},
                max_products=20,
            )
        self.assertEqual(result["platform"], "1688")
        self.assertEqual(result["snapshot_at"], "2026-08-20 10:00:00")
        product = result["products"][0]
        self.assertEqual(product["product_id"], "930671411701")
        self.assertEqual(product["price"], 0.5)
        self.assertEqual(product["total_sales"], 100000)
        self.assertEqual(product["daily_sales"], 0)
        self.assertEqual(product["is_pinned"], 1)
        self.assertEqual(product["image_url"], "https://cbu01.alicdn.com/img/ibank/example.jpg")
        self.assertEqual(product["shop_name"], "深圳市东博瑞户外用品有限公司")
