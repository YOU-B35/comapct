"""Compass snapshot batching: one in-page round trip for all date windows."""
from __future__ import annotations

from agent.douyin_tasks import _page_fetch_json_batch


def test_batch_returns_bodies_in_order():
    class FakePage:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        def evaluate(self, script, args):
            self.calls.append(args)
            return self.payload

    page = FakePage(
        [
            {"status": 200, "body": {"st": 0, "data": {"pay_amt": 1}}},
            {"status": 200, "body": {"st": 0, "data": {"pay_amt": 2}}},
            {"status": 200, "body": {"code": 0, "data": {"pay_amt": 3}}},
        ]
    )

    pairs = _page_fetch_json_batch(
        page,
        "/compass_api/shop/common/homepage/core_index_v3",
        [{"date_type": "1"}, {"date_type": "20"}, {"date_type": "21"}],
    )

    assert [body["data"]["pay_amt"] for body, err in pairs] == [1, 2, 3]
    assert all(err == "" for _, err in pairs)
    assert page.calls[0]["path"] == "/compass_api/shop/common/homepage/core_index_v3"
    assert [p["date_type"] for p in page.calls[0]["paramsList"]] == ["1", "20", "21"]


def test_batch_keeps_per_item_error_without_raising():
    class FakePage:
        def evaluate(self, script, args):
            return [
                {"status": 200, "body": {"st": 0, "data": {"pay_amt": 1}}},
                {"status": 403, "body": {"error": "forbidden"}},
                {"status": 200, "body": {"st": 40001, "msg": "参数错误"}},
                {"status": 200, "body": "not-json"},
            ]

    pairs = _page_fetch_json_batch(
        FakePage(),
        "/compass_api/shop/common/homepage/core_index_v3",
        [{"date_type": "1"}, {"date_type": "20"}, {"date_type": "21"}, {"date_type": "23"}],
    )

    assert pairs[0][0] is not None and pairs[0][1] == ""
    assert pairs[1][0] is None and "HTTP 403" in pairs[1][1]
    assert pairs[2][0] is None and "st=40001" in pairs[2][1]
    assert pairs[3][0] is None and "非 JSON" in pairs[3][1]


def test_batch_raises_when_page_returns_non_list():
    class FakePage:
        def evaluate(self, script, args):
            return {"status": 200}

    try:
        _page_fetch_json_batch(FakePage(), "/x", [{"a": "1"}])
    except RuntimeError as exc:
        assert "批量" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for non-list batch result")
