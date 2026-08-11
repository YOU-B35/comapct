"""Unit tests for Temu shop_ids allowlist filtering."""
from __future__ import annotations

import unittest

from app.temu.shop_scope import (
    filter_crawl_payload_by_shop_ids,
    filter_malls_by_shop_ids,
    normalize_shop_id_allowlist,
    shop_id_allowed,
)


class TemuShopScopeTests(unittest.TestCase):
    def test_empty_or_none_means_unrestricted(self) -> None:
        self.assertIsNone(normalize_shop_id_allowlist(None))
        self.assertIsNone(normalize_shop_id_allowlist([]))
        self.assertIsNone(normalize_shop_id_allowlist([""]))
        self.assertTrue(shop_id_allowed("any", None))

    def test_normalize_strips_and_dedupes(self) -> None:
        allow = normalize_shop_id_allowlist([" m1 ", "m2", "m1", ""])
        self.assertEqual(allow, frozenset({"m1", "m2"}))
        self.assertTrue(shop_id_allowed("m1", allow))
        self.assertFalse(shop_id_allowed("m3", allow))

    def test_filter_malls_by_shop_ids(self) -> None:
        malls = [
            {"mallId": "m1", "mallName": "A"},
            {"mallId": "m2", "mallName": "B"},
            {"mallId": "m3", "mallName": "C"},
        ]
        self.assertEqual(filter_malls_by_shop_ids(malls, None), malls)
        self.assertEqual(
            [m["mallId"] for m in filter_malls_by_shop_ids(malls, ["m2", "m3"])],
            ["m2", "m3"],
        )

    def test_filter_crawl_payload(self) -> None:
        payload = {
            "shops": [{"shop_id": "m1"}, {"shop_id": "m2"}],
            "rows": [{"shop_id": "m1", "sku": "a"}, {"shop_id": "m2", "sku": "b"}],
        }
        scoped = filter_crawl_payload_by_shop_ids(payload, ["m2"])
        self.assertEqual(scoped["shops"], [{"shop_id": "m2"}])
        self.assertEqual(scoped["rows"], [{"shop_id": "m2", "sku": "b"}])


if __name__ == "__main__":
    unittest.main()
