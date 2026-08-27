"""Douyin combined sync: orders + products + issues in one browser session."""
from __future__ import annotations

from agent import douyin_tasks as dt


def test_sync_headless_enabled_parses_env(monkeypatch):
    from app.config import sync_headless_enabled

    monkeypatch.delenv("CROSSHUB_HEADLESS", raising=False)
    assert sync_headless_enabled() is False

    monkeypatch.setenv("CROSSHUB_HEADLESS", "1")
    assert sync_headless_enabled() is True

    monkeypatch.setenv("CROSSHUB_HEADLESS", "0")
    assert sync_headless_enabled() is False


def test_run_all_sync_uses_single_browser_session(monkeypatch):
    _start, _end, day_list = dt._orders_window_24h()
    calls = {
        "launch": 0,
        "close": 0,
        "products": 0,
        "orders": 0,
        "issues": 0,
    }
    ingested: list[str] = []

    class FakeClient:
        def ingest_douyin_products(self, body):
            ingested.append("products")

        def ingest_douyin_orders(self, body):
            ingested.append("orders")

        def ingest_douyin_issues(self, body):
            ingested.append("issues")

    monkeypatch.setattr(
        dt,
        "_launch",
        lambda *a, **k: calls.__setitem__("launch", calls["launch"] + 1) or (None, None, "page"),
    )
    monkeypatch.setattr(dt, "_looks_logged_in", lambda page, context: True)
    monkeypatch.setattr(dt, "_close_pw", lambda *a, **k: calls.__setitem__("close", calls["close"] + 1))
    monkeypatch.setattr(
        dt,
        "fetch_products_via_xhr",
        lambda page: calls.__setitem__("products", calls["products"] + 1) or ([{"product_id": "P1"}], "api/products"),
    )
    monkeypatch.setattr(
        dt,
        "fetch_orders_via_xhr",
        lambda page: calls.__setitem__("orders", calls["orders"] + 1)
        or ([{"order_no": "O1", "report_day": day_list[0]}], "api/orders"),
    )

    def fake_collect_issues(page, context):
        calls["issues"] += 1
        return (
            [{"external_id": "I1", "type": "violation", "type_label": "违规"}],
            {"partial": False, "sources_ok": ["violation"], "partial_reasons": []},
        )

    import agent.douyin_issues as di

    monkeypatch.setattr(di, "collect_issues", fake_collect_issues)

    result = dt.run_all_sync(
        FakeClient(),
        {"payload": {"tenant_id": 5, "job_id": "j-all", "store_id": ""}},
    )

    assert calls["launch"] == 1
    assert calls["close"] == 1
    assert calls["products"] == 1
    assert calls["orders"] == 1
    assert calls["issues"] == 1
    assert ingested == ["products", "orders", "issues"]
    assert result["products_count"] == 1
    assert result["orders_count"] == 1
    assert result["issues_count"] == 1


def test_run_all_sync_headless_raises_when_not_logged_in(monkeypatch):
    monkeypatch.setenv("CROSSHUB_HEADLESS", "1")
    calls = {"launch": 0, "wait": 0}
    monkeypatch.setattr(
        dt,
        "_launch",
        lambda *a, **k: calls.__setitem__("launch", calls["launch"] + 1) or (None, None, "page"),
    )
    monkeypatch.setattr(dt, "_looks_logged_in", lambda page, context: False)
    monkeypatch.setattr(dt, "_wait_until_logged_in", lambda *a, **k: calls.__setitem__("wait", calls["wait"] + 1) or (False, "page"))
    monkeypatch.setattr(dt, "_close_pw", lambda *a, **k: None)

    try:
        dt.run_all_sync(
            type("C", (), {"ingest_douyin_products": lambda self, b: None,
                           "ingest_douyin_orders": lambda self, b: None,
                           "ingest_douyin_issues": lambda self, b: None})(),
            {"payload": {"tenant_id": 5, "job_id": "j", "store_id": ""}},
        )
    except RuntimeError as exc:
        assert "DY_NOT_LOGGED_IN" in str(exc)
        assert "无头" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when headless and not logged in")

    assert calls["wait"] == 0
