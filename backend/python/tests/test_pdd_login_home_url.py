"""PDD login URL routing: buyer-side monitor login must open the mobile site."""
from app.browser.pdd_context import PDD_MOBILE_HOME, PDD_SELLER_HOME, pdd_home_url

MOBILE = "https://mobile.yangkeduo.com/"


def test_buyer_login_uses_mobile_yangkeduo_home():
    assert pdd_home_url("buyer") == MOBILE
    assert PDD_MOBILE_HOME == MOBILE


def test_buyer_store_id_is_case_and_whitespace_insensitive():
    assert pdd_home_url("  Buyer ") == MOBILE
    assert pdd_home_url("BUYER") == MOBILE


def test_seller_and_default_login_keep_mms_home():
    assert pdd_home_url(None) == PDD_SELLER_HOME
    assert pdd_home_url("") == PDD_SELLER_HOME
    assert pdd_home_url("default") == PDD_SELLER_HOME
    assert pdd_home_url("123456") == PDD_SELLER_HOME
    assert PDD_SELLER_HOME == "https://mms.pinduoduo.com/"
