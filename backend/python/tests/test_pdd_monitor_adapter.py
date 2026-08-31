from app.platforms.pdd_monitor_adapter import (
    first_sales_number,
    goods_id_from_url,
    looks_auth_required,
    to_product_row,
)


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
