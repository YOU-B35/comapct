"""1688 同行爆款解析与建议规则测试。"""
from __future__ import annotations

import json

from agent.alibaba1688_peer_tasks import (
    _extract_detail_enrichment,
    _parse_compare,
    _parse_similar,
    parse_sales,
    peer_suggestion,
)


def test_parse_sales_variants() -> None:
    assert parse_sales("已售3100+件") == 3100
    assert parse_sales("已售10万+件") == 100000
    assert parse_sales("已售9600+件") == 9600
    assert parse_sales("10+件") == 10
    assert parse_sales("") == 0
    assert parse_sales(None) == 0


def test_peer_suggestion_tiers() -> None:
    assert "现象级" in peer_suggestion(100000)
    assert "重点追踪" in peer_suggestion(10000)
    assert "持续关注" in peer_suggestion(1000)
    assert "观察趋势" in peer_suggestion(100)
    assert "结合价格" in peer_suggestion(10)


def test_parse_compare_skips_current_offer() -> None:
    resp = {
        "data": {
            "offerList": [
                {"offerId": "111", "title": "A", "price": 1.2, "saleText": "已售300+件", "isCurrentOffer": False},
                {"offerId": "999", "title": "自己", "price": 0.1, "saleText": "已售3100+件", "isCurrentOffer": True},
                {"offerId": "222", "title": "B", "price": 7.5, "saleText": "已售9600+件"},
            ]
        }
    }
    items = _parse_compare(resp)
    assert len(items) == 2
    assert items[0]["sales"] == 300
    assert items[1]["sales"] == 9600
    assert all(item["offer_id"] != "999" for item in items)


def test_parse_similar_provides_shop_name() -> None:
    resp = {
        "data": {
            "data": {
                "itemList": [
                    {"itemId": "123", "shopName": "某渔具公司", "price": "6.1", "salesCount": "10+件", "linkUrl": "https://detail.1688.com/offer/123.html"}
                ]
            }
        }
    }
    out = _parse_similar(resp)
    assert out["123"]["shop_name"] == "某渔具公司"
    assert out["123"]["sales"] == 10


def test_extract_detail_enrichment_from_shopcard_and_rebuy() -> None:
    responses = [
        json.dumps({
            "data": {
                "model": {
                    "shopName": "深圳市东博瑞户外用品有限公司",
                    "qualitySatisfactionRate": "100%",
                    "shopData": [
                        {"dataKey": "品质达标率", "dataValue": "100%"},
                        {"dataKey": "店铺回头率", "dataValue": "73%"},
                    ],
                }
            }
        }, ensure_ascii=False),
        "mtopjsonp4(" + json.dumps({
            "data": {
                "data": {
                    "data": [
                        {"providerType": "RebuyRateDataProvider", "text": "商品复购率31.58%"}
                    ]
                }
            }
        }, ensure_ascii=False) + ")",
    ]
    out = _extract_detail_enrichment(responses)
    assert out["shop_name"] == "深圳市东博瑞户外用品有限公司"
    assert "复购31.58%" in out["quality_score"]
    assert "品质达标率100%" in out["quality_score"]
