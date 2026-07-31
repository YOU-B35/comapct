"""JP / multi-currency price extraction for Temu discover."""
from __future__ import annotations

import unittest

from app.crawler.competitor_crawler import extract_price
from app.crawler.competitor_discovery import build_discovery_candidates, build_search_url


class JpPriceExtractionTests(unittest.TestCase):
    def test_extract_price_parses_yen_symbol(self):
        self.assertEqual(extract_price("ルアーセット\n¥1,280\n120 sold"), 1280.0)
        self.assertEqual(extract_price("おもり\n￥298\n販売 50"), 298.0)

    def test_extract_price_parses_yen_suffix(self):
        self.assertEqual(extract_price("釣り針\n980円\n30販売"), 980.0)

    def test_build_candidates_keeps_jp_yen_products(self):
        search_url = build_search_url("fishing", "jp")
        items = [
            {
                "url": "https://www.temu.com/jp/lure-g-601.html?mall_id=111&goods_id=601",
                "text": "ソフトルアーセット\n¥1,280\n1.2K sold",
                "mallUrl": "https://www.temu.com/mall.html?mall_id=111",
            },
            {
                "url": "https://www.temu.com/jp/sinker-g-602.html?mall_id=222&goods_id=602",
                "text": "オモリ 10個\n298円\n500 sold",
                "mallUrl": "https://www.temu.com/mall.html?mall_id=222",
            },
        ]
        candidates = build_discovery_candidates(items, search_url=search_url, keyword="fishing", limit=10)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["url"], "https://www.temu.com/mall.html?mall_id=111")
        self.assertEqual(candidates[0]["sampleProducts"][0]["price"], 1280.0)
        self.assertEqual(candidates[1]["sampleProducts"][0]["price"], 298.0)

    def test_build_candidates_skips_non_product_urls(self):
        search_url = build_search_url("fishing", "jp")
        items = [
            {
                "url": "https://www.temu.com/jp",
                "text": "ナビ\n¥409\n730 sold",
                "mallUrl": "",
            },
            {
                "url": "https://www.temu.com/jp/lure-g-601.html?goods_id=601",
                "text": "ソフトルアー\n¥1,280\n120 sold",
                "mallUrl": "",
            },
        ]
        candidates = build_discovery_candidates(items, search_url=search_url, keyword="fishing", limit=10)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["sampleProductCount"], 1)
        self.assertIn("g-601", candidates[0]["sampleProducts"][0]["url"])


if __name__ == "__main__":
    unittest.main()
