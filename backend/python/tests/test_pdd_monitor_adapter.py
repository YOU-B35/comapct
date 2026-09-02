from app.platforms.pdd_monitor_adapter import (
    _target_config,
    collect_products,
    ensure_pinned_products,
    first_sales_number,
    goods_id_from_url,
    goods_page_expired,
    looks_auth_required,
    to_product_row,
)


class FakeHandle:
    def __init__(self, href, text):
        self._href = href
        self._text = text

    def get_attribute(self, name):
        return self._href if name == "href" else None

    def inner_text(self, **kwargs):
        return self._text

    def evaluate(self, script):
        return self._text


class FakePage:
    def __init__(self, handles=None, goto_raises=False):
        self._handles = handles or []
        self._goto_raises = goto_raises

    def wait_for_selector(self, selector, **kwargs):
        if not self._handles:
            raise Exception("no handles")

    def locator(self, selector):
        return self

    def element_handles(self):
        return self._handles

    def goto(self, url, **kwargs):
        if self._goto_raises:
            raise Exception("nav failed")

    def wait_for_timeout(self, ms):
        pass

    def inner_text(self, selector, **kwargs):
        return "爆款商品 ￥19.9 2.3万人已拼 商品详情"

    def get_attribute(self, selector, name):
        return None


def test_goods_id_from_url_supports_relative_and_absolute_urls():
    assert goods_id_from_url("/goods.html?goods_id=123&mall_id=9") == "123"
    assert goods_id_from_url("https://mobile.yangkeduo.com/goods.html?goods_id=abc") == "abc"


def test_to_product_row_extracts_price_and_sales_text():
    row = to_product_row(
        "123",
        "/goods.html?goods_id=123",
        "爆款拖鞋 ￥19.9 2.3万人已拼",
        "https://mobile.yangkeduo.com/mall_page.html?mall_id=9",
        1,
    )
    assert row["product_id"] == "123"
    assert row["price"] == 19.9
    assert row["total_sales"] == 23000
    assert row["sale_text"] == "2.3万人已拼"
    assert row["url"] == "https://mobile.yangkeduo.com/goods.html?goods_id=123"


def test_first_sales_number_handles_plain_counts():
    assert first_sales_number("已拼 88 件") == 88


def test_looks_auth_required_detects_login_pages_and_risk_text():
    assert looks_auth_required("https://mobile.yangkeduo.com/login.html", "")
    assert looks_auth_required("https://mobile.yangkeduo.com/goods.html", "请先登录后继续")


def test_target_config_parses_json_and_ignores_invalid():
    assert _target_config({"config_json": '{"top_n":5,"pinned_offer_ids":["111"]}'}) == {
        "top_n": 5,
        "pinned_offer_ids": ["111"],
    }
    assert _target_config({"config_json": "not-json"}) == {}
    assert _target_config({}) == {}


def test_collect_products_marks_pinned_ids():
    page = FakePage([
        FakeHandle("/goods.html?goods_id=111", "商品A ￥10 100人已拼"),
        FakeHandle("/goods.html?goods_id=222", "商品B ￥20 200人已拼"),
    ])
    rows = collect_products(
        page,
        "https://mobile.yangkeduo.com/mall_page.html?mall_id=9",
        10,
        pinned_ids=["111"],
    )
    assert [r["product_id"] for r in rows] == ["111", "222"]
    assert rows[0]["is_pinned"] == 1
    assert rows[1]["is_pinned"] == 0


def test_ensure_pinned_products_appends_missing_pinned_fallback_row():
    page = FakePage(handles=[], goto_raises=True)
    rows = ensure_pinned_products(
        page,
        "https://mobile.yangkeduo.com/mall_page.html?mall_id=9",
        [],
        ["999"],
    )
    assert len(rows) == 1
    assert rows[0]["product_id"] == "999"
    assert rows[0]["is_pinned"] == 1
    assert rows[0]["url"] == "https://mobile.yangkeduo.com/goods.html?goods_id=999&mall_id=9"
    assert rows[0]["status"] == "onsale"
    assert rows[0]["expired"] == 0


def test_goods_page_expired_detects_delisted_copy():
    assert goods_page_expired("该商品已失效，去看看其他商品吧")
    assert goods_page_expired("商品已下架")
    assert not goods_page_expired("爆款商品 ￥19.9 2.3万人已拼")
