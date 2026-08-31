"""Tests for 1688 mtop transient-failure retry."""
from __future__ import annotations

import pytest

from agent.alibaba1688_order_tasks import _mtop


class _FakeContext:
    def __init__(self):
        self.evaluate_calls = 0

    def cookies(self):
        return [{"name": "_m_h5_tk", "value": "token123_suffix"}]


class _FakePage:
    def __init__(self, fail_times: int = 0):
        self.context = _FakeContext()
        self.evaluate_calls = 0
        self.fail_times = fail_times

    def evaluate(self, js, arg):
        self.evaluate_calls += 1
        if self.evaluate_calls <= self.fail_times:
            raise TimeoutError("browser closed")
        return {"ret": ["SUCCESS::调用成功"], "data": {}}


def test_mtop_retries_transient_evaluate_failure():
    page = _FakePage(fail_times=1)
    result = _mtop(page, "mtop.1688.trading.dataline.service", {"page": 1})
    assert result["ret"][0].startswith("SUCCESS")
    assert page.evaluate_calls == 2


def test_mtop_does_not_retry_business_error():
    page = _FakePage(fail_times=0)
    result = _mtop(page, "mtop.1688.trading.dataline.service", {})
    assert result["ret"][0].startswith("SUCCESS")
    assert page.evaluate_calls == 1


def test_mtop_raises_after_retries_exhausted():
    page = _FakePage(fail_times=99)
    with pytest.raises(TimeoutError):
        _mtop(page, "mtop.1688.trading.dataline.service", {})
    assert page.evaluate_calls == 2
