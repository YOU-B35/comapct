"""Amazon 写回操作回归测试：FBA 订单不发货，跟踪号输入框选择器加固。"""
from __future__ import annotations

import re

from app.amazon.write_actions import (
    TRACKING_INPUT_SELECTORS,
    _find_tracking_input,
    supports_ship_action,
)


class FakeLocator:
    """按 selector 关键字返回命中的假 locator。"""

    def __init__(self, selector: str = "", hit: bool = False):
        self.selector = selector
        self._hit = hit

    def count(self) -> int:
        return 1 if self._hit else 0

    @property
    def first(self) -> "FakeLocator":
        return self

    def locator(self, selector: str) -> "FakeLocator":
        return FakeLocator(selector, self._hit and "tracking" in selector.lower())

    def get_by_role(self, role: str, **kwargs) -> "FakeLocator":
        return FakeLocator(role, False)

    def filter(self, **kwargs) -> "FakeLocator":
        return self


class FakePage:
    def __init__(self, matching: set[str]):
        self.matching = matching
        self._last_selector = ""

    def locator(self, selector: str) -> FakeLocator:
        self._last_selector = selector
        return FakeLocator(selector, any(token in selector.lower() for token in self.matching))

    def get_by_role(self, role: str, **kwargs) -> FakeLocator:
        return FakeLocator(role, False)


def test_supports_ship_action_only_for_merchant_fulfilled() -> None:
    assert supports_ship_action("fbm") is True
    assert supports_ship_action("mfn") is True
    assert supports_ship_action("merchant") is True
    assert supports_ship_action("fba") is False
    assert supports_ship_action("amazon") is False
    # 未知类型允许继续走 DOM，避免误拦
    assert supports_ship_action("") is True
    assert supports_ship_action(None) is True


def test_tracking_selectors_cover_aria_and_zh() -> None:
    joined = " ".join(TRACKING_INPUT_SELECTORS)
    assert "aria-label*='tracking'" in joined
    assert "运单" in joined
    assert "carrier" in joined


def test_find_tracking_input_picks_aria_labeled_input() -> None:
    page = FakePage({"aria-label*='tracking'"})
    locator = _find_tracking_input(page)
    assert locator is not None
    assert "aria-label" in locator.selector


def test_find_tracking_input_returns_none_when_absent() -> None:
    page = FakePage(set())
    assert _find_tracking_input(page) is None


def test_find_tracking_input_excludes_search_box_fallback() -> None:
    page = FakePage({"input[type='text']"})
    found = _find_tracking_input(page)
    # 不能直接命中任意文本框兜底：必须排除搜索框后才允许兜底
    assert found is None or re.search(r"tracking|carrier|运单|追踪", found.selector, re.I)
