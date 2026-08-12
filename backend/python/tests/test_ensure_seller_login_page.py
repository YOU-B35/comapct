"""ensure_seller_login_page keeps only Temu seller tabs and navigates to TEMU_SELLER_HOME."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.browser.context import ensure_seller_login_page, is_temu_seller_url


def test_is_temu_seller_url_accepts_seller_hosts():
    assert is_temu_seller_url("https://agentseller.temu.com/main/order")
    assert is_temu_seller_url("https://seller.kuajingmaihuo.com/login")
    assert not is_temu_seller_url("https://www.dianxiaomi.com/")
    assert not is_temu_seller_url("about:blank")


def test_ensure_seller_login_page_closes_foreign_tabs_and_navigates():
    foreign = MagicMock()
    foreign.url = "https://www.dianxiaomi.com/user/login.htm"
    temu = MagicMock()
    temu.url = "https://agentseller.temu.com/"
    context = MagicMock()
    context.pages = [foreign, temu]

    with patch("app.browser.context.TEMU_SELLER_HOME", "https://agentseller.temu.com/"), \
            patch("app.browser.context.time.sleep", return_value=None):
        page = ensure_seller_login_page(context, force_navigate=True)

    assert foreign.close.call_count >= 1
    assert temu.goto.called
    assert temu.goto.call_args.args[0] == "https://agentseller.temu.com/"
    assert temu.bring_to_front.called
    assert page is temu


def test_ensure_seller_login_page_opens_new_tab_when_none():
    context = MagicMock()
    context.pages = []
    new_page = MagicMock()
    new_page.url = "https://agentseller.temu.com/"
    context.new_page.return_value = new_page

    with patch("app.browser.context.TEMU_SELLER_HOME", "https://agentseller.temu.com/"), \
            patch("app.browser.context.time.sleep", return_value=None):
        page = ensure_seller_login_page(context, force_navigate=True)

    assert context.new_page.called
    assert new_page.goto.called
    assert page is new_page
