import unittest

from app.platforms.alibaba1688_monitor_utils import (
    canonicalize_offer_url,
    canonicalize_shop_url,
    offer_id_from_url,
    parse_price,
    parse_sales_text,
)


class Alibaba1688MonitorUtilsTest(unittest.TestCase):
    def test_canonicalize_shop_url(self):
        self.assertEqual(
            canonicalize_shop_url("https://shop16yx1905b2433.1688.com"),
            "https://shop16yx1905b2433.1688.com",
        )
        self.assertEqual(
            canonicalize_shop_url("shop16yx1905b2433.1688.com"),
            "https://shop16yx1905b2433.1688.com",
        )
        with self.assertRaises(ValueError):
            canonicalize_shop_url("https://detail.1688.com/offer/930671411701.html")

    def test_offer_url_helpers(self):
        self.assertEqual(
            offer_id_from_url("https://detail.1688.com/offer/930671411701.html"),
            "930671411701",
        )
        self.assertEqual(
            canonicalize_offer_url("https://m.1688.com/offer/930671411701.html"),
            "https://detail.1688.com/offer/930671411701.html",
        )
        with self.assertRaises(ValueError):
            canonicalize_offer_url("https://shop16yx1905b2433.1688.com")

    def test_parse_sales_text(self):
        self.assertEqual(parse_sales_text("已售10+件"), 10)
        self.assertEqual(parse_sales_text("已售10万+件"), 100000)
        self.assertEqual(parse_sales_text("成交246,920件"), 246920)
        self.assertEqual(parse_sales_text(""), 0)

    def test_parse_price(self):
        self.assertEqual(parse_price("¥7.8"), 7.8)
        self.assertEqual(parse_price(""), 0.0)
