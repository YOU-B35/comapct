"""Amazon orders-v3: paginate via the ?page= URL param instead of clicking next."""
from __future__ import annotations

from app.amazon.crawlers.orders_v3 import _order_page_url


def test_order_page_url_replaces_page_param():
    assert (
        _order_page_url("https://sellercentral.amazon.com/orders-v3/?page=1", 2)
        == "https://sellercentral.amazon.com/orders-v3/?page=3"
    )
    assert (
        _order_page_url("https://sellercentral.amazon.com/orders-v3/unshipped?page=1", 0)
        == "https://sellercentral.amazon.com/orders-v3/unshipped?page=1"
    )
    assert (
        _order_page_url("https://sellercentral.amazon.com/orders-v3/fba/pending?page=1", 4)
        == "https://sellercentral.amazon.com/orders-v3/fba/pending?page=5"
    )
