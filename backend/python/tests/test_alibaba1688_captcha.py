from types import SimpleNamespace

from agent.alibaba1688_product_tasks import (
    _pause_for_manage_mini_captcha,
    _recover_manage_mini_captcha,
    looks_like_1688_captcha,
    relaunch_headed_if_needed,
    should_relaunch_headed,
)

PUNISH_URL = "https://offer.1688.com/offer/manage_mini.vm/_____tmd_____/punish?pureCaptcha="
SPA_URL = "https://offer.1688.com/app/pages-group/manage-home/index.html"


class FakePage:
    def __init__(self, url: str):
        self.url = url
        self.wait_calls = 0
        self.gotos: list[str] = []
        self.context = SimpleNamespace(cookies=lambda: [])

    def content(self) -> str:
        return "<html></html>"

    def wait_for_timeout(self, _ms: int) -> None:
        self.wait_calls += 1
        if looks_like_1688_captcha(url=self.url) and self.wait_calls >= 2:
            self.url = SPA_URL

    def goto(self, url: str, **_kwargs) -> None:
        self.gotos.append(url)
        self.url = url

    def bring_to_front(self) -> None:
        return None


def test_looks_like_1688_captcha_from_punish_url():
    assert looks_like_1688_captcha(url=PUNISH_URL)


def test_looks_like_1688_captcha_from_validate_body():
    assert looks_like_1688_captcha(body='{"ret":["FAIL_SYS_USER_VALIDATE","被挤爆"]}')


def test_looks_like_1688_captcha_ignores_normal_payload():
    assert not looks_like_1688_captcha(url="https://work.1688.com/home", body='{"items":[]}')


def test_should_relaunch_headed_when_headless_hits_captcha():
    assert should_relaunch_headed(headless=True, captcha=True) is True


def test_should_not_relaunch_when_already_headed():
    assert should_relaunch_headed(headless=False, captcha=True) is False


def test_should_not_relaunch_twice():
    assert should_relaunch_headed(headless=True, captcha=True, already_relaunched=True) is False


def test_should_not_relaunch_without_captcha():
    assert should_relaunch_headed(headless=True, captcha=False) is False


def test_relaunch_headed_closes_then_opens_visible_chrome():
    closed = []
    launched = []

    def close(pw, context):
        closed.append((pw, context))

    def launch(tenant_id, *, headless, goto):
        launched.append({"tenant_id": tenant_id, "headless": headless, "goto": goto})
        page = FakePage(goto)
        return ("pw2", "ctx2", page)

    pw, ctx, page, headless, relaunched = relaunch_headed_if_needed(
        tenant_id=5,
        goto="https://work.1688.com/home/page/index.htm",
        pw="pw1",
        context="ctx1",
        page=FakePage("https://work.1688.com/"),
        headless=True,
        already_relaunched=False,
        launch=launch,
        close=close,
    )
    assert closed == [("pw1", "ctx1")]
    assert launched == [
        {"tenant_id": 5, "headless": False, "goto": "https://work.1688.com/home/page/index.htm"}
    ]
    assert headless is False
    assert relaunched is True
    assert pw == "pw2"
    assert ctx == "ctx2"
    assert page.url.endswith("index.htm")


def test_relaunch_headed_is_noop_when_already_visible():
    def close(*_a):
        raise AssertionError("should not close")

    def launch(*_a, **_k):
        raise AssertionError("should not launch")

    page = FakePage("https://work.1688.com/")
    pw, ctx, out, headless, relaunched = relaunch_headed_if_needed(
        tenant_id=5,
        goto="https://work.1688.com/",
        pw="pw1",
        context="ctx1",
        page=page,
        headless=False,
        already_relaunched=False,
        launch=launch,
        close=close,
    )
    assert (pw, ctx, out, headless, relaunched) == ("pw1", "ctx1", page, False, False)


def test_pause_waits_until_punish_url_clears():
    page = FakePage(PUNISH_URL)
    box: dict = {}
    out = _pause_for_manage_mini_captcha(page, box, on_captcha=None)
    assert out is page
    assert box["captcha_hits"] == 1
    assert not looks_like_1688_captcha(url=page.url)
    assert page.wait_calls >= 2


def test_pause_switches_to_on_captcha_page(monkeypatch):
    old = FakePage(PUNISH_URL)
    new = FakePage("https://work.1688.com/")
    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._goto_manage_spa",
        lambda p: p.gotos.append("spa"),
    )
    box: dict = {}
    out = _pause_for_manage_mini_captcha(old, box, on_captcha=lambda: new)
    assert out is new
    assert new.gotos == ["spa"]


def test_recover_relaunches_when_page_already_on_punish():
    page = FakePage(PUNISH_URL)
    headed = FakePage("https://work.1688.com/")
    calls = []

    def on_captcha():
        calls.append(True)
        headed.url = SPA_URL
        return headed

    box: dict = {}
    out = _recover_manage_mini_captcha(page, box, on_captcha)
    assert calls == [True]
    assert out is headed
    assert box["captcha_hits"] == 1


def test_recover_skips_when_page_is_clean():
    page = FakePage("https://work.1688.com/")
    box: dict = {}

    def boom():
        raise AssertionError("should not relaunch")

    out = _recover_manage_mini_captcha(page, box, on_captcha=boom)
    assert out is page
    assert box.get("captcha_hits", 0) == 0


def test_growth_tabs_retry_same_tab_after_captcha(monkeypatch):
    from agent.alibaba1688_product_tasks import _fetch_growth_tab_pages

    calls: list[str] = []
    headed = FakePage(SPA_URL)

    def fake_fetch(page, **kwargs):
        stage = str(kwargs.get("stamp_growth_stage") or "")
        calls.append(stage)
        if stage == "qlsp" and calls.count("qlsp") == 1:
            return [], None, True
        return [{"offerId": len(calls), "subject": stage, "lifePeriod": "valid"}], 1, False

    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._browser_fetch_manage_mini_all", fake_fetch
    )
    monkeypatch.setattr("agent.alibaba1688_product_tasks._resolve_csrf", lambda _p: "tok")
    monkeypatch.setattr("agent.alibaba1688_product_tasks._goto_manage_spa", lambda p: None)
    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._wait_out_manage_mini_captcha",
        lambda _p, timeout_ms=0: None,
    )
    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._capture_spa_manage_mini_extras",
        lambda _p, _u: {},
    )

    box: dict = {"rows": [], "captcha_hits": 0, "manage_mini_hits": 0}
    counts = _fetch_growth_tab_pages(
        FakePage(SPA_URL),
        box,
        csrf="tok",
        catalog_unique=0,
        on_captcha=lambda: headed,
    )
    assert box["captcha_hits"] == 1
    assert calls[0] == "qlsp"
    assert calls.count("qlsp") == 2
    assert counts["potential"] == 1
    assert counts["index4"] == 1
    assert counts["yanxuan"] == 1
    assert len(box["rows"]) == 3


def test_growth_tabs_stamp_when_larger_than_previous_tab(monkeypatch):
    from agent.alibaba1688_product_tasks import _fetch_growth_tab_pages

    def fake_fetch(page, **kwargs):
        stage = str(kwargs.get("stamp_growth_stage") or "")
        n = 7 if stage == "qlsp" else 30
        return (
            [{"offerId": f"{stage}-{i}", "subject": stage, "lifePeriod": "valid"} for i in range(n)],
            n,
            False,
        )

    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._browser_fetch_manage_mini_all", fake_fetch
    )
    monkeypatch.setattr("agent.alibaba1688_product_tasks._resolve_csrf", lambda _p: "tok")
    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._capture_spa_manage_mini_extras",
        lambda _p, _u: {"filter": "growthStage:" + _u.split("growthStage=")[-1][:8]},
    )

    box: dict = {"rows": [], "captcha_hits": 0, "manage_mini_hits": 0}
    counts = _fetch_growth_tab_pages(
        FakePage(SPA_URL),
        box,
        csrf="tok",
        catalog_unique=502,
        allow_captcha_wait=False,
    )
    assert counts["potential"] == 7
    assert counts["index4"] == 30
    assert counts["yanxuan"] == 30
    assert len(box["rows"]) == 67
