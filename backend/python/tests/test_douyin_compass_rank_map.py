from agent.douyin_compass_rank import (
    BOARD_RANK_API,
    DATE_WINDOW_DATE_TYPE,
    flatten_api_row,
    map_rank_row,
    normalize_board,
    normalize_date_window,
)


def test_normalize_board():
    assert normalize_board("搜索榜") == "search"
    assert normalize_board("product_card") == "product_card"
    assert normalize_board("总榜") == "total"


def test_normalize_date_window():
    assert normalize_date_window("today") == "today"
    assert normalize_date_window("昨日") == "yesterday"


def test_map_rank_row_extracts_core_fields():
    raw = {
        "product_id": "p1",
        "product_name": "钩",
        "shop_name": "YOTO",
        "pay_amt": 12.5,
        "product_click_cnt": 10,
        "pay_cnt": 2,
        "product_click_pay_cnt_ratio": 0.2,
        "product_show_cnt": 100,
        "pay_order_cnt": 2,
    }
    out = map_rank_row(raw, 1)
    assert out["product_id"] == "p1"
    assert out["shop_name"] == "YOTO"
    assert out["rank_no"] == 1
    assert out["pay_amt"] == 12.5
    assert out["click_cnt"] == 10


def test_probed_board_constants():
    assert DATE_WINDOW_DATE_TYPE["today"] == 1
    assert DATE_WINDOW_DATE_TYPE["yesterday"] == 20
    assert "search" in BOARD_RANK_API["search"]
    assert "product_card_hot" in BOARD_RANK_API["product_card"]
    assert "market_hot_sale" in BOARD_RANK_API["total"]


def test_flatten_product_card_row():
    row = {
        "rank": 2,
        "pay_amt": {"value_range": [{"unit": "price", "value": 10000}, {"unit": "price", "value": 20000}]},
        "product_click_cnt": {"value_range": [{"unit": "number", "value": 10}, {"unit": "number", "value": 20}]},
        "pay_combo_cnt": {"value_range": [{"unit": "number", "value": 1}, {"unit": "number", "value": 3}]},
        "click_pay_rate": {"value_range": [{"unit": "ratio", "value": 0.1}, {"unit": "ratio", "value": 0.2}]},
        "product_info": {"id": "pid9", "name": "竿", "image": "http://img"},
        "shop_info": {"shop_name": "店A"},
    }
    flat = flatten_api_row("product_card", row)
    mapped = map_rank_row(flat, 2)
    assert mapped["product_id"] == "pid9"
    assert mapped["product_name"] == "竿"
    assert mapped["shop_name"] == "店A"
    assert mapped["pay_amt"] == 150.0  # fen midpoint / 100
    assert mapped["click_cnt"] == 15.0
    assert mapped["click_pay_cvr"] == 0.15
    assert mapped["deal_cnt"] == 2.0
    assert mapped["order_cnt"] == 2.0  # pay_cnt missing → pay_combo fallback
    assert mapped["pay_cnt"] == 2.0


def test_flatten_product_card_yesterday_empty_show_and_pay_cnt():
    """Compass product_card date_type=20 often returns empty {} for show_cnt/pay_cnt."""
    row = {
        "rank": 1,
        "pay_amt": {"value_range": [{"unit": "price", "value": 10000}, {"unit": "price", "value": 20000}]},
        "product_click_cnt": {"value_range": [{"unit": "number", "value": 10}, {"unit": "number", "value": 20}]},
        "pay_cnt": {},
        "show_cnt": {},
        "pay_combo_cnt": {"value_range": [{"unit": "number", "value": 100}, {"unit": "number", "value": 250}]},
        "click_pay_rate": {"value_range": [{"unit": "ratio", "value": 0.01}, {"unit": "ratio", "value": 0.02}]},
        "product_info": {"id": "pidY", "name": "昨日品", "image": "http://img"},
        "shop_info": {"shop_name": "店Y"},
    }
    flat = flatten_api_row("product_card", row)
    mapped = map_rank_row(flat, 1)
    assert mapped["show_cnt"] is None
    assert mapped["deal_cnt"] == 175.0
    assert mapped["order_cnt"] == 175.0
    assert mapped["pay_cnt"] == 175.0
    assert flat.get("_show_cnt_empty") is True
    assert flat.get("_pay_cnt_empty") is True


def test_parse_compete_core_index_extra_value_band():
    from agent.douyin_compass_rank import parse_compete_core_index

    body = {
        "st": 0,
        "data": [
            {
                "metrics": {
                    "dh_product_show_uv": {
                        "extra_value": {
                            "lower": {"unit": "number", "value": 5000},
                            "upper": {"unit": "number", "value": 10000},
                        },
                        "value": {"unit": "number", "value": 0},
                    },
                    "pay_cnt": {
                        "extra_value": {
                            "lower": {"unit": "number", "value": 100},
                            "upper": {"unit": "number", "value": 250},
                        },
                        "value": {"unit": "number", "value": 0},
                    },
                    "pay_combo_cnt": {
                        "extra_value": {
                            "lower": {"unit": "number", "value": 200},
                            "upper": {"unit": "number", "value": 400},
                        },
                        "value": {"unit": "number", "value": 0},
                    },
                }
            }
        ],
    }
    parsed = parse_compete_core_index(body)
    assert parsed["show_cnt"] == 7500.0
    assert parsed["order_cnt"] == 175.0
    assert parsed["deal_cnt"] == 300.0
