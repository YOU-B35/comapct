from app.browser.alibaba1688_context import crawl_headless_enabled
from agent.alibaba1688_product_constants import assert_products_xhr_ready


def test_crawl_defaults_to_headless(monkeypatch):
    monkeypatch.delenv("A1688_HEADED", raising=False)
    assert crawl_headless_enabled() is True


def test_crawl_headed_when_env_set(monkeypatch):
    monkeypatch.setenv("A1688_HEADED", "1")
    assert crawl_headless_enabled() is False


def test_gate_raises_when_not_ready(monkeypatch):
    monkeypatch.setattr("agent.alibaba1688_product_constants.PRODUCTS_XHR_READY", False)
    try:
        assert_products_xhr_ready()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "A1688_PRODUCTS_NEED_DAY0" in str(exc)
