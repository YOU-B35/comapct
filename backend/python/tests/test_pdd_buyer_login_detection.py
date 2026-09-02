"""PDD buyer-side login detection must use mobile-site markers/domain."""
from agent.pdd_tasks import _looks_logged_in


class FakeBuyerPage:
    url = "https://mobile.yangkeduo.com/"

    def inner_text(self, selector, **kwargs):
        return "首页 分类 购物车 我的 搜索"


class FakeSellerPage:
    url = "https://mms.pinduoduo.com/"

    def inner_text(self, selector, **kwargs):
        return "首页 商品 数据 拼多多商家 订单"


class FakeLoginPage:
    url = "https://mobile.yangkeduo.com/login.html"

    def inner_text(self, selector, **kwargs):
        return "扫码登录 拼多多"


class FakeContext:
    def __init__(self, cookies):
        self._cookies = cookies

    def cookies(self):
        return self._cookies


def test_buyer_page_detects_logged_in_with_buyer_cookie():
    context = FakeContext([{"name": "pdd_user_id", "domain": ".yangkeduo.com"}])
    assert _looks_logged_in(FakeBuyerPage(), context, buyer=True)


def test_buyer_login_page_with_auth_cookie_is_logged_in():
    # 登录完成后页面仍停留在 login/next 地址时，认证 cookie 仍是已登录的强信号
    context = FakeContext([{"name": "PDDAccessToken", "domain": ".yangkeduo.com"}])
    assert _looks_logged_in(FakeLoginPage(), context, buyer=True)


def test_buyer_detection_requires_auth_cookies():
    # 买家首页导航文案未登录也可见，不能用文案兜底
    assert not _looks_logged_in(FakeBuyerPage(), FakeContext([]), buyer=True)


def test_buyer_cookie_on_foreign_domain_is_ignored():
    context = FakeContext([{"name": "pdd_user_id", "domain": ".example.com"}])
    assert not _looks_logged_in(FakeBuyerPage(), context, buyer=True)


def test_buyer_cookie_keyword_fallback_covers_unknown_auth_names():
    context = FakeContext([{"name": "pd_user_token_v2", "domain": ".yangkeduo.com"}])
    assert _looks_logged_in(FakeBuyerPage(), context, buyer=True)


def test_seller_page_still_detected_with_seller_check():
    context = FakeContext([{"name": "PASS_ID", "domain": ".pinduoduo.com"}])
    assert _looks_logged_in(FakeSellerPage(), context)


def test_seller_detection_without_cookies_uses_markers():
    assert _looks_logged_in(FakeSellerPage(), FakeContext([]))


def test_login_cta_without_cookie_is_not_logged_in():
    assert not _looks_logged_in(FakeLoginPage(), FakeContext([]))
