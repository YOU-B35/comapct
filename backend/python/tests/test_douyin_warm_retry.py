"""First-page retry after warm-up so transient session init errors don't abort a sync."""
from __future__ import annotations

from agent.douyin_tasks import _call_with_retry


def test_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("session not warm yet")
        return "ok"

    assert _call_with_retry(flaky, delay=0, label="page0") == "ok"
    assert calls["n"] == 2


def test_retry_raises_after_all_attempts_exhausted():
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise RuntimeError("boom")

    try:
        _call_with_retry(always_fail, retries=1, delay=0, label="page0")
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    assert calls["n"] == 2


def test_retry_zero_attempts_calls_once():
    calls = {"n": 0}

    def once():
        calls["n"] += 1
        raise RuntimeError("boom")

    try:
        _call_with_retry(once, retries=0, delay=0, label="page0")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert calls["n"] == 1
