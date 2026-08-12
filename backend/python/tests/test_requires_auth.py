"""requires_auth must not treat the whole kuajingmaihuo seller console as login."""
from app.browser.context import requires_auth


def test_requires_auth_agentseller_auth_path():
    assert requires_auth("https://agentseller.temu.com/auth/authentication")
    assert requires_auth("https://agentseller.temu.com/login")


def test_requires_auth_kuajingmaihuo_login_only():
    assert requires_auth("https://seller.kuajingmaihuo.com/login")
    assert requires_auth("https://seller.kuajingmaihuo.com/settle/passport")
    assert not requires_auth("https://seller.kuajingmaihuo.com/")
    assert not requires_auth("https://seller.kuajingmaihuo.com/main/order-manager")


def test_requires_auth_agentseller_home_not_auth():
    assert not requires_auth("https://agentseller.temu.com/")
    assert not requires_auth("https://agentseller.temu.com/main/order")
