"""Default-category cache for Compass product-rank: capture once, reuse later."""
from __future__ import annotations

from agent import douyin_compass_rank as dcr


def _cache_file(tmp_path):
    return tmp_path / "compass-rank-cache.json"


def test_save_and_load_default_category_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(dcr, "_default_category_cache_path", lambda: _cache_file(tmp_path))

    dcr.save_default_category_cache(
        5,
        "default",
        {"industry_id": "1001", "category_id": "2002", "category_name": "服饰内衣"},
    )

    cats = dcr.load_default_category_cache(5, "default")
    assert cats == {
        "industry_id": "1001",
        "category_id": "2002",
        "category_name": "服饰内衣",
    }


def test_load_missing_cache_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(dcr, "_default_category_cache_path", lambda: _cache_file(tmp_path))

    assert dcr.load_default_category_cache(5, "default") == {}


def test_cache_isolated_per_tenant_and_store(tmp_path, monkeypatch):
    monkeypatch.setattr(dcr, "_default_category_cache_path", lambda: _cache_file(tmp_path))
    dcr.save_default_category_cache(
        5,
        "default",
        {"industry_id": "1001", "category_id": "2002", "category_name": "A"},
    )
    dcr.save_default_category_cache(
        5,
        "s2",
        {"industry_id": "3003", "category_id": "4004", "category_name": "B"},
    )

    assert dcr.load_default_category_cache(5, "default")["category_id"] == "2002"
    assert dcr.load_default_category_cache(5, "s2")["category_id"] == "4004"
    assert dcr.load_default_category_cache(7, "default") == {}


def test_clear_default_category_cache_removes_only_own_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(dcr, "_default_category_cache_path", lambda: _cache_file(tmp_path))
    dcr.save_default_category_cache(
        5,
        "default",
        {"industry_id": "1001", "category_id": "2002", "category_name": "A"},
    )
    dcr.save_default_category_cache(
        5,
        "s2",
        {"industry_id": "3003", "category_id": "4004", "category_name": "B"},
    )

    dcr.clear_default_category_cache(5, "default")

    assert dcr.load_default_category_cache(5, "default") == {}
    assert dcr.load_default_category_cache(5, "s2")["category_id"] == "4004"


def test_run_compass_rank_sync_reuses_cached_category(tmp_path, monkeypatch):
    """When a cached default category exists, skip the per-run capture listener."""
    import agent.douyin_tasks as dt

    monkeypatch.setattr(dcr, "_default_category_cache_path", lambda: _cache_file(tmp_path))
    dcr.save_default_category_cache(
        5,
        "s1",
        {"industry_id": "111", "category_id": "222", "category_name": "缓存类目"},
    )

    capture_calls = {"n": 0}
    slice_args = []

    def fake_capture(page):
        capture_calls["n"] += 1
        return {"industry_id": "999", "category_id": "888", "category_name": "不应使用"}

    class FakeClient:
        def __init__(self):
            self.ingested = []

        def ingest_douyin_compass_product_rank(self, body):
            self.ingested.append(body)

    def fake_fetch_board_slice(
        page,
        *,
        board,
        date_window,
        limit,
        industry_id,
        category_id,
        category_name,
    ):
        slice_args.append(
            {
                "board": board,
                "date_window": date_window,
                "industry_id": industry_id,
                "category_id": category_id,
                "category_name": category_name,
            }
        )
        return (
            [{"product_id": f"{board}-{date_window}-p1"}],
            {
                "report_day": "2026-08-26",
                "category_id": category_id,
                "category_name": category_name,
                "source_url": "https://compass.jinritemai.com/shop/chance/rank-product",
            },
        )

    monkeypatch.setattr(dt, "_launch", lambda *a, **k: (None, None, "page"))
    monkeypatch.setattr(dt, "_looks_logged_in", lambda page, context: True)
    monkeypatch.setattr(dt, "_close_pw", lambda *a, **k: None)
    monkeypatch.setattr(dt, "_resolve_store_id", lambda client, tenant_id, store_id: "s1")
    monkeypatch.setattr(dcr, "_capture_default_category", fake_capture)
    monkeypatch.setattr(dcr, "fetch_board_slice", fake_fetch_board_slice)
    monkeypatch.setattr(
        dcr,
        "enrich_products_with_compete_core_index",
        lambda *a, **k: {"filled_show": 0, "filled_order": 0},
    )

    client = FakeClient()
    result = dcr.run_compass_product_rank_sync(
        client,
        {"payload": {"tenant_id": 5, "job_id": "j1", "store_id": ""}},
    )

    assert capture_calls["n"] == 0
    assert result["industry_id"] == "111"
    assert result["category_id"] == "222"
    assert slice_args
    assert all(s["industry_id"] == "111" and s["category_id"] == "222" for s in slice_args)
    assert len(client.ingested) == 6
