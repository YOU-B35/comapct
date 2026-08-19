import json

from agent.alibaba1688_product_tasks import _normalize_row, _parse_gateway_body


def test_parse_offer_growth_nested_gateway():
    payload = {
        "api": "mtop.alibaba.cbu.workdiordatareaderservice.getvaluesfromgateway",
        "data": {
            "CDT_demo": {
                "dataCode": "CDT_demo",
                "values": {
                    "offerGrowthGetOfferListService": {
                        "success": True,
                        "value": {
                            "result": {
                                "data": {
                                    "total": 2,
                                    "data": [
                                        {
                                            "offerId": 1001,
                                            "title": "demo sku a",
                                            "hotSalePrice": "1.2",
                                            "growthStage": "all",
                                        },
                                        {
                                            "offerId": 1002,
                                            "title": "demo sku b",
                                            "hotSalePrice": "3.4",
                                            "growthStage": "qlsp",
                                        },
                                    ],
                                }
                            }
                        },
                    }
                },
            }
        },
        "ret": ["SUCCESS::调用成功"],
    }
    rows = _parse_gateway_body(json.dumps(payload, ensure_ascii=False))
    assert len(rows) == 2
    assert rows[0]["offerId"] == 1001
    assert rows[1]["title"] == "demo sku b"


def test_parse_rejects_captcha_body():
    body = json.dumps(
        {
            "ret": ["FAIL_SYS_USER_VALIDATE", "RGV587_ERROR::SM::哎哟喂,被挤爆啦,请稍后重试"],
            "data": {"url": "https://offer.1688.com/offer/manage_mini.vm/_____tmd_____/punish?pureCaptcha="},
        }
    )
    assert _parse_gateway_body(body) == []


def test_parse_manage_mini_body_pagination_fields():
    from agent.alibaba1688_product_tasks import _parse_manage_mini_body

    body = json.dumps(
        {
            "msgType": "success",
            "totalCount": 430,
            "currentPage": 1,
            "pageSize": 50,
            "items": [
                {
                    "offerId": 9001,
                    "subject": "manage mini sku",
                    "itemNumber": "MM-1",
                    "lifePeriod": "valid",
                    "canBookedAmount": 12,
                    "referBpriceStr": "9.9",
                }
            ],
        },
        ensure_ascii=False,
    )
    rows, total, captcha = _parse_manage_mini_body(body)
    assert not captcha
    assert total == 430
    assert len(rows) == 1
    assert rows[0]["offerId"] == 9001
    mapped = _normalize_row(rows[0], default_status="on_sale")
    assert mapped is not None
    assert mapped["offer_id"] == "9001"
    assert mapped["product_name"] == "manage mini sku"
    assert mapped["status"] == "on_sale"


def test_normalize_maps_life_period_status_buckets():
    sold = _normalize_row(
        {"offerId": "1", "subject": "售罄", "lifePeriod": "sellOut"},
        default_status="",
    )
    pending = _normalize_row(
        {"offerId": "2", "subject": "待上架", "lifePeriod": "expired"},
        default_status="",
    )
    draft = _normalize_row(
        {"offerId": "3", "subject": "草稿", "lifePeriod": "draft"},
        default_status="",
    )
    named = _normalize_row(
        {"offerId": "4", "subject": "上架", "statusName": "上架中", "lifePeriod": "valid"},
        default_status="",
    )
    assert sold and sold["status"] == "sold_out"
    assert pending and pending["status"] == "pending_list"
    assert draft and draft["status"] == "draft"
    assert named and named["status"] == "on_sale"


def test_all_bucket_item_stamped_from_status_fetch():
    """lifePeriod=all 的商品，进入售罄桶后应记为 sold_out。"""
    row = {
        "offerId": "8",
        "subject": "售罄商品",
        "lifePeriod": "all",
        "pictureURL": "https://cbu01.alicdn.com/img/ibank/demo.jpg",
    }
    item_lp = str(row.get("lifePeriod") or "").strip()
    if "sellOut" != "all" and item_lp in ("", "all"):
        row["lifePeriod"] = "sellOut"
    mapped = _normalize_row(row, default_status="")
    assert mapped and mapped["status"] == "sold_out"
    assert mapped["image_url"].startswith("https://")


def test_item_life_period_not_overwritten_by_fetch_bucket():
    """Simulate sellOut fetch returning a still-valid item — keep item lifePeriod."""
    row = {
        "offerId": "9",
        "subject": "仍在售",
        "lifePeriod": "valid",
        "statusName": "上架中",
        "offerStatusValue": "published",
    }
    # what we used to do wrongly: stamp sellOut
    stamped = dict(row)
    # correct path: do not stamp over existing
    if not str(stamped.get("lifePeriod") or "").strip():
        stamped["lifePeriod"] = "sellOut"
    mapped = _normalize_row(stamped, default_status="")
    assert mapped and mapped["status"] == "on_sale"


def test_normalize_picks_https_image_url():
    mapped = _normalize_row(
        {
            "offerId": "55",
            "subject": "带图商品",
            "lifePeriod": "valid",
            "pictureURL": "http://img.china.alibaba.com/img/ibank/demo.jpg",
        }
    )
    assert mapped is not None
    assert mapped["image_url"].startswith("https://")
    assert "cbu01.alicdn.com" in mapped["image_url"]
    assert "demo.jpg" in mapped["image_url"]


def test_normalize_picks_size_url_when_picture_is_empty_dict():
    mapped = _normalize_row(
        {
            "offerId": "1071393370892",
            "subject": "新款欧鲤钓偏转件",
            "statusName": "上架中",
            "offerStatusValue": "published",
            "pictureURL": {},
            "size310x310URL": {},
            "size100x100URL": (
                "http://img.china.alibaba.com/img/ibank/"
                "O1CN01l3WT6p9BiSE2BxHU_!!2219577180417-0-cib.summ.jpg"
            ),
            "summURL": (
                "http://img.china.alibaba.com/img/ibank/"
                "O1CN01l3WT6p9BiSE2BxHU_!!2219577180417-0-cib.64x64.jpg"
            ),
        }
    )
    assert mapped is not None
    assert mapped["image_url"].startswith("https://cbu01.alicdn.com/")
    assert "summ.jpg" in mapped["image_url"]
    assert mapped["status"] == "on_sale"

    mapped = _normalize_row(
        {
            "item_id": "1071393370892",
            "title": "新款欧鲤钓偏转件",
            "hotSalePrice": "0.18",
            "growthStage": "all",
            "lifeCycle": "yanxuan_growth",
            "yxIndex": "1.84",
            "yx_zhishu": "1.9",
            "zs_yx_dissatisfy_threshold": "Y",
            "offer_url": "http://detail.1688.com/offer/1071393370892.html",
            "xy_item_rate_info_json": (
                '{"item_new_buy_uv_30d":"8","se_expo_uv_7d":"4","se_expo_pv_7d":"12"}'
            ),
        },
        default_status="on_sale",
    )
    assert mapped is not None
    assert mapped["offer_id"] == "1071393370892"
    assert mapped["product_name"] == "新款欧鲤钓偏转件"
    assert mapped["price"] == "0.18"
    assert mapped["status"] == "on_sale"
    assert mapped["index_score"] == "1.84"
    assert mapped["tag_yanxuan"] == 1
    assert mapped["tag_underperform"] == 0
    assert mapped["search_expose_7d"] in (4, "4")
    assert mapped["visitor_30d"] in (8, "8")


def test_qlsp_stamps_potential_not_yanxuan():
    mapped = _normalize_row(
        {"offerId": "11", "subject": "潜力", "growthStage": "qlsp"},
        default_status="on_sale",
        scope="potential",
    )
    assert mapped and mapped["tag_potential"] == 1
    assert mapped["tag_yanxuan"] == 0


def test_yx_index_alone_does_not_mark_yanxuan():
    mapped = _normalize_row(
        {"offerId": "12", "subject": "指数", "yxIndex": "4.1", "growthStage": "all"},
        default_status="on_sale",
    )
    assert mapped and mapped["index_score"] == "4.1"
    assert mapped["tag_yanxuan"] == 0


def test_index4_scope_fills_index_score():
    mapped = _normalize_row(
        {"offerId": "13", "subject": "指数4", "growthStage": "cgzsspyjg"},
        default_status="on_sale",
        scope="index4",
    )
    assert mapped and mapped["index_score"] == "4.0"


def test_manage_mini_url_includes_growth_filter():
    from agent.alibaba1688_product_tasks import _build_manage_mini_url

    url = _build_manage_mini_url(
        csrf="abc",
        life_period="valid",
        page=2,
        page_size=20,
        extra_qs={"filter": "item_growth_caigou_index:4~;"},
    )
    assert "lifePeriod=valid" in url
    assert "currentPage=2" in url
    assert "item_growth_caigou_index" in url


def test_specific_life_period_beats_generic_published():
    mapped = _normalize_row(
        {
            "offerId": "13",
            "subject": "售罄无中文状态",
            "lifePeriod": "sellOut",
            "offerStatusValue": "published",
        }
    )
    assert mapped and mapped["status"] == "sold_out"


def test_status_name_wins_over_echoed_sellout_life_period():
    mapped = _normalize_row(
        {
            "offerId": "10",
            "subject": "仍在售",
            "lifePeriod": "sellOut",
            "statusName": "上架中",
            "offerStatusValue": "published",
        }
    )
    assert mapped and mapped["status"] == "on_sale"


def test_stamped_status_bucket_overrides_onsale_status_name():
    """状态桶确认有效后会强制 statusName；此时应按桶状态入库。"""
    from agent.alibaba1688_product_tasks import LIFE_PERIOD_STATUS_NAME

    mapped = _normalize_row(
        {
            "offerId": "14",
            "subject": "真实待上架",
            "lifePeriod": "expired",
            "statusName": LIFE_PERIOD_STATUS_NAME["expired"],
            "offerStatusValue": "published",
            "pictureURL": "//cbu01.alicdn.com/img/ibank/demo.jpg",
        }
    )
    assert mapped and mapped["status"] == "pending_list"
    assert mapped["image_url"].startswith("https://")


def test_status_name_maps_pending_and_sold_out_from_all_tab():
    pending = _normalize_row(
        {"offerId": "11", "subject": "待上架商品", "lifePeriod": "all", "statusName": "待上架"}
    )
    sold = _normalize_row(
        {"offerId": "12", "subject": "售罄商品", "lifePeriod": "all", "statusName": "库存售罄"}
    )
    assert pending and pending["status"] == "pending_list"
    assert sold and sold["status"] == "sold_out"


def test_skip_ingest_when_status_tab_returns_full_catalog():
    from agent.alibaba1688_product_tasks import should_ingest_life_period_rows

    assert should_ingest_life_period_rows("all", 502, 502) is True
    assert should_ingest_life_period_rows("sellOut", 502, 502) is False
    assert should_ingest_life_period_rows("expired", 18, 502) is True
    assert should_ingest_life_period_rows("valid", 30, 7) is True


def test_stamp_subset_bucket_even_when_status_name_still_onsale():
    from agent.alibaba1688_product_tasks import should_stamp_life_period

    echoed = [{"statusName": "上架中"}] * 10
    assert (
        should_stamp_life_period(
            life_period="expired",
            fetched_n=18,
            catalog_unique=502,
            sample_rows=echoed,
        )
        is True
    )
    assert (
        should_stamp_life_period(
            life_period="sellOut",
            fetched_n=502,
            catalog_unique=502,
            sample_rows=echoed,
        )
        is False
    )


def test_growth_filter_compares_against_full_catalog_not_previous_tab():
    from agent.alibaba1688_product_tasks import growth_filter_likely_ignored

    # 潜力已写入 7 条后，指数 tab 返回 30 条 —— 这是真实子集，不能当「未过滤」跳过
    assert growth_filter_likely_ignored(30, catalog_unique=7) is False
    assert growth_filter_likely_ignored(30, catalog_unique=502) is False
    assert growth_filter_likely_ignored(7, catalog_unique=502) is False
    assert growth_filter_likely_ignored(502, catalog_unique=502) is True
    assert growth_filter_likely_ignored(7, catalog_unique=0) is False
    # 潜力常见 478/512 ≈93%，必须入库，不能再用 85% 误判
    assert growth_filter_likely_ignored(478, catalog_unique=512) is False
    assert growth_filter_likely_ignored(480, catalog_unique=0) is False
    assert growth_filter_likely_ignored(510, catalog_unique=512) is True


def test_pick_price_from_unit_price_and_range():
    from agent.alibaba1688_product_tasks import _pick_price

    assert _pick_price({"referBpriceStr": "", "unitPrice": "0.18"}) == "0.18"
    assert _pick_price({"priceSumDispaly": "0.17~0.18", "unitPrice": "0.18"}) == "0.17~0.18"
    assert (
        _pick_price({"priceRangeJsonConfig": "[[100,0.18],[1000,0.17]]", "referBpriceStr": ""})
        == "0.17~0.18"
    )


def test_normalize_row_reads_unit_price_when_refer_b_empty():
    mapped = _normalize_row(
        {
            "offerId": "1071393370892",
            "subject": "新款欧鲤钓偏转件",
            "statusName": "上架中",
            "referBpriceStr": "",
            "unitPrice": "0.18",
            "priceSumDispaly": "0.17~0.18",
            "size100x100URL": "http://img.china.alibaba.com/img/ibank/demo.summ.jpg",
        }
    )
    assert mapped is not None
    assert mapped["price"] == "0.17~0.18"
    assert mapped["image_url"].startswith("https://")
    assert "_100x100" not in mapped["image_url"]
    assert mapped["image_url"].endswith(".jpg")


def test_upgrade_1688_thumb_url_drops_cdn_size_suffix():
    from agent.alibaba1688_product_tasks import _normalize_image_url, _pick_image_url

    assert (
        _normalize_image_url("https://cbu01.alicdn.com/img/ibank/demo.jpg_100x100.jpg")
        == "https://cbu01.alicdn.com/img/ibank/demo.jpg"
    )
    assert (
        _normalize_image_url(
            "https://cbu01.alicdn.com/img/ibank/O1CN01demo-0-cib.64x64.jpg"
        )
        == "https://cbu01.alicdn.com/img/ibank/O1CN01demo-0-cib.summ.jpg"
    )
    picked = _pick_image_url(
        {
            "size100x100URL": "https://cbu01.alicdn.com/img/ibank/tiny.jpg_100x100.jpg",
            "pictureURL": "https://cbu01.alicdn.com/img/ibank/full.jpg",
        }
    )
    assert picked == "https://cbu01.alicdn.com/img/ibank/full.jpg"


def test_growth_tab_specs_use_verified_growth_stage_codes():
    from agent.alibaba1688_product_tasks import GROWTH_TAB_SPECS

    by_scope = {s["scope"]: s for s in GROWTH_TAB_SPECS}
    assert by_scope["potential"]["life_period"] == "qlsp"
    assert by_scope["index4"]["life_period"] == "cgzsspyjg"
    assert by_scope["yanxuan"]["life_period"] == "growthyxp"
    assert all(s["show_type"] == "valid" for s in GROWTH_TAB_SPECS)
    assert all(not s.get("extra_qs") for s in GROWTH_TAB_SPECS)


def test_growth_manage_mini_urls_use_verified_life_period():
    from agent.alibaba1688_product_tasks import GROWTH_TAB_SPECS, _build_manage_mini_url

    urls = {
        spec["scope"]: _build_manage_mini_url(
            csrf="TOKEN",
            life_period=spec["life_period"],
            page=1,
            page_size=50,
        )
        for spec in GROWTH_TAB_SPECS
    }

    assert "growthStage=" not in "\n".join(urls.values())
    assert "lifePeriod=qlsp" in urls["potential"]
    assert "lifePeriod=cgzsspyjg" in urls["index4"]
    assert "lifePeriod=growthyxp" in urls["yanxuan"]


def test_manage_mini_life_periods_use_one_full_catalog_bucket():
    from agent.alibaba1688_product_tasks import MANAGE_MINI_LIFE_PERIODS

    assert MANAGE_MINI_LIFE_PERIODS == ("all",)

def test_stamp_status_bucket_rows_forces_chinese_status_name():
    from agent.alibaba1688_product_tasks import stamp_status_bucket_rows

    rows = stamp_status_bucket_rows(
        [
            {
                "offerId": "1",
                "subject": "待上架",
                "lifePeriod": "valid",
                "statusName": "上架中",
                "offerStatusValue": "published",
            }
        ],
        life_period="expired",
        stamp=True,
    )
    mapped = _normalize_row(rows[0], default_status="")
    assert mapped and mapped["status"] == "pending_list"


def test_merge_prefers_specific_status_over_on_sale():
    from agent.alibaba1688_product_tasks import _merge_row

    dst = {"offer_id": "1", "status": "on_sale", "tag_potential": 0, "tag_yanxuan": 0, "tag_underperform": 0}
    src = {"offer_id": "1", "status": "sold_out", "tag_potential": 0, "tag_yanxuan": 0, "tag_underperform": 0}
    _merge_row(dst, src)
    assert dst["status"] == "sold_out"


def test_merge_on_sale_does_not_wipe_pending_list():
    from agent.alibaba1688_product_tasks import _merge_row

    dst = {"offer_id": "1", "status": "pending_list", "tag_potential": 0, "tag_yanxuan": 0, "tag_underperform": 0}
    src = {"offer_id": "1", "status": "on_sale", "tag_potential": 0, "tag_yanxuan": 0, "tag_underperform": 0}
    _merge_row(dst, src)
    assert dst["status"] == "pending_list"


def test_merge_or_tags_and_index_score():
    from agent.alibaba1688_product_tasks import _merge_row

    dst = {
        "offer_id": "1",
        "status": "on_sale",
        "tag_potential": 0,
        "tag_yanxuan": 0,
        "tag_underperform": 0,
        "index_score": "",
    }
    src = {
        "offer_id": "1",
        "status": "on_sale",
        "tag_potential": 1,
        "tag_yanxuan": 0,
        "tag_underperform": 0,
        "index_score": "4.0",
    }
    _merge_row(dst, src)
    assert dst["tag_potential"] == 1
    assert dst["index_score"] == "4.0"


def test_parse_flowdatas_gmv_1d():
    from agent.alibaba1688_product_tasks import _apply_flows, _parse_flowdatas, _normalize_row

    body = json.dumps({
        "data": {
            "data": {
                "9001": [
                    {"fieldName": "今日GMV", "value": "88.5"},
                    {"fieldName": "30天GMV", "value": "1000"},
                ]
            }
        }
    }, ensure_ascii=False)
    flows = _parse_flowdatas(body)
    assert flows["9001"]["gmv_1d"] == "88.5"
    assert flows["9001"]["gmv_30d"] == "1000"

    mapped = _normalize_row(
        {"offerId": "9001", "subject": "x", "lifePeriod": "valid"},
        default_status="on_sale",
    )
    assert mapped is not None
    assert mapped.get("gmv_1d") in (None, "")
    mapped["offer_id"] = "9001"
    _apply_flows(mapped, flows)
    assert mapped.get("gmv_1d") == "88.5"


def test_normalize_row_reads_gmv_1d():
    from_raw = _normalize_row(
        {"offerId": "9001", "subject": "x", "lifePeriod": "valid", "gmv_1d": "10"},
        default_status="on_sale",
    )
    assert from_raw is not None
    assert from_raw["gmv_1d"] == "10"

    from_alias = _normalize_row(
        {"offerId": "9002", "subject": "x", "lifePeriod": "valid", "gmv1d": "11"},
        default_status="on_sale",
    )
    assert from_alias is not None
    assert from_alias["gmv_1d"] == "11"

    from_rates = _normalize_row(
        {
            "offerId": "9003",
            "subject": "x",
            "lifePeriod": "valid",
            "xy_item_rate_info_json": '{"gmv_1d":"12"}',
        },
        default_status="on_sale",
    )
    assert from_rates is not None
    assert from_rates["gmv_1d"] == "12"


def test_merge_row_copies_gmv_1d():
    from agent.alibaba1688_product_tasks import _merge_row

    dst = {
        "offer_id": "1",
        "status": "on_sale",
        "tag_potential": 0,
        "tag_yanxuan": 0,
        "tag_underperform": 0,
        "gmv_1d": "",
    }
    src = {
        "offer_id": "1",
        "status": "on_sale",
        "tag_potential": 0,
        "tag_yanxuan": 0,
        "tag_underperform": 0,
        "gmv_1d": "12.3",
    }
    _merge_row(dst, src)
    assert dst["gmv_1d"] == "12.3"



def test_filtered_fetch_stops_after_probe_when_filter_is_ignored(monkeypatch):
    from agent.alibaba1688_product_tasks import _fetch_filtered_manage_mini_pages

    calls = []

    def fake_fetch(page, **kwargs):
        calls.append(kwargs.get("max_pages"))
        return ([{"offerId": str(i)} for i in range(50)], 502, False)

    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._browser_fetch_manage_mini_all", fake_fetch
    )

    rows, total, captcha = _fetch_filtered_manage_mini_pages(
        object(),
        csrf="tok",
        life_period="valid",
        stamp_growth_stage="qlsp",
        catalog_unique=502,
    )

    assert captcha is False
    assert total == 502
    assert len(rows) == 50
    assert calls == [1]


def test_filtered_fetch_expands_real_subset_with_bounded_pages(monkeypatch):
    from agent.alibaba1688_product_tasks import _fetch_filtered_manage_mini_pages

    calls = []

    def fake_fetch(page, **kwargs):
        calls.append(kwargs.get("max_pages"))
        if kwargs.get("max_pages") == 1:
            return ([{"offerId": "1"}], 118, False)
        return ([{"offerId": str(i)} for i in range(118)], 118, False)

    monkeypatch.setattr(
        "agent.alibaba1688_product_tasks._browser_fetch_manage_mini_all", fake_fetch
    )

    rows, total, captcha = _fetch_filtered_manage_mini_pages(
        object(),
        csrf="tok",
        life_period="expired",
        catalog_unique=502,
        page_size=50,
    )

    assert captcha is False
    assert total == 118
    assert len(rows) == 118
    assert calls == [1, 3]

def test_all_catalog_uses_verified_valid_show_type():
    from agent.alibaba1688_product_tasks import show_type_for_life_period

    assert show_type_for_life_period("all") == "valid"


def test_product_category_specs_cover_backend_tabs():
    from agent.alibaba1688_product_tasks import PRODUCT_CATEGORY_SPECS

    assert {spec["code"] for spec in PRODUCT_CATEGORY_SPECS} == {
        "status_on_sale",
        "status_pending_list",
        "status_sold_out",
        "status_reviewing",
        "status_violation_off",
        "status_draft",
        "growth_potential",
        "growth_yanxuan",
        "growth_index",
    }


def test_product_category_specs_use_verified_manage_mini_params():
    from agent.alibaba1688_product_tasks import PRODUCT_CATEGORY_SPECS

    by_code = {spec["code"]: spec for spec in PRODUCT_CATEGORY_SPECS}
    assert by_code["status_on_sale"]["show_type"] == "valid"
    assert by_code["status_pending_list"]["show_type"] == "expired"
    assert by_code["status_sold_out"]["show_type"] == "valid"
    assert by_code["status_sold_out"]["extra_qs"] == {"isSellOut": "true"}
    assert by_code["status_reviewing"]["show_type"] == "auditing"
    assert by_code["status_violation_off"]["show_type"] == "untread"
    assert by_code["status_draft"]["show_type"] == "draft"
    assert by_code["growth_potential"]["life_period"] == "qlsp"
    assert by_code["growth_index"]["life_period"] == "cgzsspyjg"
    assert by_code["growth_yanxuan"]["life_period"] == "growthyxp"
    assert {spec["life_period"] for spec in PRODUCT_CATEGORY_SPECS} == {
        "all",
        "qlsp",
        "cgzsspyjg",
        "growthyxp",
    }


def test_category_offer_ids_extract_only_catalog_members():
    from agent.alibaba1688_product_tasks import category_offer_ids

    rows = [
        {"offerId": "1", "subject": "a"},
        {"offer_id": "2", "subject": "b"},
        {"offerId": "outside", "subject": "c"},
        {"subject": "missing"},
    ]
    assert category_offer_ids(rows, {"1", "2"}) == ["1", "2"]


def test_unfiltered_growth_category_response_is_rejected():
    from agent.alibaba1688_product_tasks import category_result

    result = category_result(
        code="growth_potential",
        rows=[{"offerId": str(i)} for i in range(100)],
        total=100,
        catalog_offer_ids={str(i) for i in range(100)},
        elapsed_ms=10,
    )
    assert result["status"] == "failed"
    assert result["error_code"] == "A1688_CATEGORY_FILTER_IGNORED"
    assert "offer_ids" not in result


def test_failed_category_has_no_empty_offer_ids():
    from agent.alibaba1688_product_tasks import failed_category_result

    result = failed_category_result("A1688_CATEGORY_TIMEOUT", 123)
    assert result == {
        "status": "failed",
        "error_code": "A1688_CATEGORY_TIMEOUT",
        "elapsed_ms": 123,
    }


def test_sync_product_categories_returns_nine_relation_sets():
    from agent.alibaba1688_product_tasks import sync_product_categories

    calls = []

    def fake_fetch(_page, **kwargs):
        calls.append((kwargs.get("life_period"), kwargs.get("show_type"), kwargs.get("extra_qs")))
        life_period = kwargs.get("life_period")
        extra_qs = kwargs.get("extra_qs") or {}
        if life_period == "qlsp":
            rows = [{"offerId": "1"}]
        elif life_period == "cgzsspyjg":
            rows = [{"offerId": "2"}]
        elif life_period == "growthyxp":
            rows = [{"offerId": "3"}]
        elif extra_qs.get("isSellOut") == "true":
            rows = [{"offerId": "4"}]
        elif kwargs.get("show_type") == "valid":
            rows = [{"offerId": "1"}, {"offerId": "2"}, {"offerId": "3"}, {"offerId": "4"}]
        else:
            rows = [{"offerId": "2"}]
        return rows, len(rows), False

    results = sync_product_categories(
        object(),
        {"1", "2", "3", "4"},
        deadline=10_000_000_000,
        csrf="tok",
        fetch_fn=fake_fetch,
    )

    assert len(results) == 9
    assert results["status_on_sale"]["offer_ids"] == ["1", "2", "3", "4"]
    assert results["status_sold_out"]["offer_ids"] == ["4"]
    assert results["growth_potential"]["offer_ids"] == ["1"]
    assert results["growth_index"]["offer_ids"] == ["2"]
    assert results["growth_yanxuan"]["offer_ids"] == ["3"]
    assert all(result["status"] == "success" for result in results.values())
    assert len(calls) == 9


def test_growth_category_recaptures_platform_request_when_static_filter_is_ignored():
    import agent.alibaba1688_product_tasks as tasks

    fetch_calls = []
    captured_spas = []

    def fake_fetch(_page, **kwargs):
        extra_qs = kwargs.get("extra_qs") or {}
        fetch_calls.append(extra_qs)
        if extra_qs.get("platformToken") == "captured":
            return [{"offerId": "1"}], 1, False
        return [{"offerId": str(i)} for i in range(30)], 30, False

    rows, total, captcha = tasks._fetch_growth_category_pages(
        object(),
        spec={
            "scope": "potential",
            "spa": "https://offer.1688.com/app/demo?growthStage=qlsp",
            "life_period": "valid",
            "growth_stage": "qlsp",
            "extra_qs": {"filter": "item_growth_caigou_index:0.0001~3.9999;"},
        },
        csrf="tok",
        catalog_unique=30,
        fetch_fn=fake_fetch,
        capture_fn=lambda _page, spa: captured_spas.append(spa) or {
            "platformToken": "captured"
        },
        resolve_csrf_fn=lambda _page: "tok",
    )

    assert captcha is False
    assert total == 1
    assert rows == [{"offerId": "1"}]
    assert captured_spas == ["https://offer.1688.com/app/demo?growthStage=qlsp"]
    assert fetch_calls == [
        {"filter": "item_growth_caigou_index:0.0001~3.9999;"},
        {
            "platformToken": "captured",
            "filter": "item_growth_caigou_index:0.0001~3.9999;",
        },
    ]


def test_sync_product_categories_marks_timeout_without_empty_replacement():
    from agent.alibaba1688_product_tasks import sync_product_categories

    results = sync_product_categories(
        object(),
        {"1"},
        deadline=0,
        csrf="tok",
        fetch_fn=lambda *_args, **_kwargs: pytest.fail("fetch must not run after deadline"),
    )

    assert len(results) == 9
    assert all(result["status"] == "failed" for result in results.values())
    assert all(result["error_code"] == "A1688_CATEGORY_TIMEOUT" for result in results.values())
    assert all("offer_ids" not in result for result in results.values())


def test_ingest_proxy_adds_category_diagnostics_and_partial():
    from agent.alibaba1688_product_tasks import _CategoryIngestClient

    class Client:
        def __init__(self):
            self.payload = None

        def ingest_1688_products(self, payload):
            self.payload = payload
            return {"ok": True}

    client = Client()
    proxy = _CategoryIngestClient(
        client,
        sync_id="agt_demo",
        categories={
            "growth_potential": {"status": "success", "offer_ids": ["1"], "count": 1, "elapsed_ms": 2},
            "growth_yanxuan": {"status": "failed", "error_code": "A1688_CATEGORY_TIMEOUT", "elapsed_ms": 3},
        },
    )
    proxy.ingest_1688_products({"store_id": "default", "products": []})

    assert client.payload["sync_id"] == "agt_demo"
    assert client.payload["partial"] is True
    assert client.payload["categories"]["growth_potential"]["offer_ids"] == ["1"]
    assert "offer_ids" not in client.payload["categories"]["growth_yanxuan"]


def test_category_result_rejects_empty_invalid_response():
    from agent.alibaba1688_product_tasks import category_result

    result = category_result(
        code="status_pending_list",
        rows=[],
        total=None,
        catalog_offer_ids={"1"},
        elapsed_ms=5,
    )
    assert result["status"] == "failed"
    assert result["error_code"] == "A1688_CATEGORY_INVALID_RESPONSE"
    assert "offer_ids" not in result


def test_category_result_marks_truncated_pagination_as_failed():
    from agent.alibaba1688_product_tasks import category_result

    result = category_result(
        code="growth_potential",
        rows=[{"offerId": str(i)} for i in range(200)],
        total=479,
        catalog_offer_ids={str(i) for i in range(500)},
        elapsed_ms=5,
    )
    assert result["status"] == "failed"
    assert result["error_code"] == "A1688_CATEGORY_PARTIAL_RESPONSE"
    assert "offer_ids" not in result


def test_on_sale_reuses_full_catalog_without_refetch(monkeypatch):
    import agent.alibaba1688_product_tasks as tasks

    calls = []

    def full_fetch(_page, **kwargs):
        calls.append(("full", kwargs.get("life_period")))
        return [{"offerId": str(i)} for i in range(502)], 502, False

    def filtered_fetch(_page, **kwargs):
        calls.append(("filtered", kwargs.get("life_period")))
        return [], 0, False

    monkeypatch.setattr(tasks, "_browser_fetch_manage_mini_all", full_fetch)
    monkeypatch.setattr(tasks, "_fetch_filtered_manage_mini_pages", filtered_fetch)
    results = tasks.sync_product_categories(
        object(),
        {str(i) for i in range(502)},
        deadline=10_000_000_000,
        csrf="tok",
    )

    assert results["status_on_sale"]["count"] == 502
    assert not any(call[0] == "full" for call in calls)
