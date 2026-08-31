"""Tests for 1688 offer-detail static enrichment cache helpers."""
from __future__ import annotations

from pathlib import Path

from app.cache_store import CacheStore
from app.platforms.alibaba1688_shop_collector import (
    _apply_cached_enrichment,
    _enrichment_fields,
    _load_enrich_cache,
    _offer_detail_cache_enabled,
    _save_enrich_cache,
)


def test_enrichment_fields_returns_only_static_subset():
    row = {
        "offer_id": "1001",
        "title": "demo",
        "image_url": "https://x/img.jpg",
        "shop_name": "shop-a",
        "quality_rate": "98%",
        "price": "1.2",
        "total_sales": 999,
        "rank": 3,
    }
    fields = _enrichment_fields(row)
    assert fields["title"] == "demo"
    assert fields["shop_name"] == "shop-a"
    assert "price" not in fields
    assert "total_sales" not in fields
    assert "rank" not in fields


def test_apply_cached_enrichment_fills_missing_fields():
    row = {"offer_id": "1001", "title": "demo"}
    cached = {"shop_name": "shop-a", "quality_rate": "98%", "price": "ignored"}
    skipped = _apply_cached_enrichment(row, cached)
    assert skipped is True
    assert row["shop_name"] == "shop-a"
    assert row["quality_rate"] == "98%"
    assert "price" not in row


def test_apply_cached_enrichment_returns_false_for_invalid():
    row = {"offer_id": "1001"}
    assert _apply_cached_enrichment(row, None) is False
    assert _apply_cached_enrichment(row, {}) is False
    assert row == {"offer_id": "1001"}


def test_load_save_roundtrip(tmp_path: Path):
    store = CacheStore(tmp_path / "cache.json")
    row = {
        "offer_id": "1001",
        "shop_name": "shop-a",
        "rebuy_rate": "30%",
        "price": "1.2",
    }
    _save_enrich_cache(store, tenant_id=5, offer_id="1001", row=row)
    cached = _load_enrich_cache(store, tenant_id=5, offer_id="1001")
    assert cached is not None
    assert cached["shop_name"] == "shop-a"
    assert "price" not in cached


def test_load_missing_returns_none(tmp_path: Path):
    store = CacheStore(tmp_path / "cache.json")
    assert _load_enrich_cache(store, tenant_id=5, offer_id="nope") is None


def test_offer_detail_cache_disabled_for_pinned():
    assert _offer_detail_cache_enabled("1001", pinned=[]) is True
    assert _offer_detail_cache_enabled("1001", pinned=["1001"]) is False
