from agent.douyin_issues import map_issue_row, map_product_diag_row, map_violation_row


def test_map_violation_row():
    raw = {
        "ticket_id": "7665195347521585434",
        "violation_reason": "商家超时未履约开票义务",
        "circumstances_level": "1",
        "info": {
            "object": {
                "object_id": "6927056386721677137",
                "object_name": "反吹成品线组",
                "object_imgs": [
                    "https://p3-aio.ecombdimg.com/obj/ecom-shop-material/a.png",
                    "https://p3-aio.ecombdimg.com/obj/ecom-shop-material/b.png",
                ],
            },
            "violation_time": 1784692395,
            "violation_detail": "存在超时未开发票行为",
        },
    }
    out = map_issue_row("violation", raw)
    assert out is not None
    assert out["external_id"] == "7665195347521585434"
    assert out["type"] == "violation"
    assert out["priority"] == "high"
    assert "开票" in out["detail"]
    assert out["product_name"] == "反吹成品线组"
    assert out["reported_at"].startswith("2026-")
    assert out["product_image"] == "https://p3-aio.ecombdimg.com/obj/ecom-shop-material/a.png"


def test_map_product_diag_row():
    raw = {
        "product_id": "3770610134485697774",
        "product_name": "Feeder加强版",
        "img": "https://p3-aio.ecombdimg.com/obj/ecom-shop-material/cover.jpg",
        "product_pic": [
            "https://p3-aio.ecombdimg.com/obj/ecom-shop-material/pic1.jpg",
            "https://p9-aio.ecombdimg.com/obj/ecom-shop-material/pic2.jpg",
        ],
        "problem_num_to_improve": 2,
        "name_doc": ["商品缺少讲解回放", "重要属性未全部填写，请补充"],
        "affect_doc": ["影响商品转化"],
    }
    out = map_product_diag_row(raw, now="2026-08-14 12:00:00")
    assert out is not None
    assert out["external_id"] == "product:3770610134485697774"
    assert out["type"] == "product"
    assert out["priority"] == "medium"
    assert "讲解回放" in out["detail"]
    assert out["reported_at"] == "2026-08-14 12:00:00"
    assert out["product_image"] == "https://p3-aio.ecombdimg.com/obj/ecom-shop-material/cover.jpg"


def test_map_product_image_falls_back_to_product_pic():
    raw = {
        "product_id": "p2",
        "product_name": "无封面",
        "problem_num_to_improve": 1,
        "name_doc": ["缺属性"],
        "product_pic": ["https://cdn.example/1.jpg"],
    }
    out = map_product_diag_row(raw, now="2026-08-14 12:00:00")
    assert out["product_image"] == "https://cdn.example/1.jpg"


def test_map_product_skips_clean():
    assert map_product_diag_row({"product_id": "1", "problem_num_to_improve": 0, "name_doc": []}) is None


def test_map_violation_requires_ticket_id():
    assert map_violation_row({"violation_reason": "x"}) is None
