"""Mock data generators for PDD testing (本地开发用)."""
from datetime import datetime, timedelta, time
from typing import Any
from zoneinfo import ZoneInfo
import random
import uuid

SHANGHAI = ZoneInfo("Asia/Shanghai")


def generate_mock_orders(
    tenant_id: int,
    date_window: str = "today",
    store_id: str | None = None,
    count: int = 20
) -> list[dict[str, Any]]:
    """Generate mock PDD orders for testing."""
    now = datetime.now(SHANGHAI)
    orders = []

    # 根据时间窗口计算订单日期范围
    if date_window == "today":
        start_date = now.date()
        end_date = now.date()
    elif date_window == "d1":
        start_date = (now - timedelta(days=1)).date()
        end_date = now.date()
    elif date_window == "d7":
        start_date = (now - timedelta(days=7)).date()
        end_date = now.date()
    elif date_window == "d30":
        start_date = (now - timedelta(days=30)).date()
        end_date = now.date()
    else:
        start_date = now.date()
        end_date = now.date()

    # 生成订单
    for i in range(count):
        order_date = start_date + timedelta(
            days=random.randint(0, (end_date - start_date).days)
        )
        order_time = datetime.combine(
            order_date,
            datetime.min.time().replace(
                hour=random.randint(0, 23),
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            ),
            tzinfo=SHANGHAI
        )

        paid_amount = round(random.uniform(50, 500), 2)
        refund_amount = round(random.uniform(0, paid_amount * 0.3), 2) if random.random() > 0.7 else 0

        order = {
            "order_no": f"PDD{order_date.strftime('%Y%m%d')}{1000 + i}",
            "order_key": f"PDD{order_date.strftime('%Y%m%d')}{1000 + i}",
            "external_shop_id": "",
            "store_id": store_id or f"store-{tenant_id}-1",
            "buyer_masked": f"买家{i+1:02d}****",
            "paid_amount": str(paid_amount),
            "refunded_amount": str(refund_amount),
            "status": random.choice(["待发货", "已发货", "已收货", "已取消"]),
            "product_name": f"测试商品{random.randint(1, 50)}",
            "quantity": random.randint(1, 5),
            "created_at": order_time.isoformat(),
            "ordered_at": order_time.isoformat(),
            "paid_at": order_time.isoformat(),
            "shipped_at": (order_time + timedelta(days=1)).isoformat() if random.random() > 0.2 else None,
            "received_at": (order_time + timedelta(days=3)).isoformat() if random.random() > 0.3 else None,
            "refunded_at": None,
            "channel": "拼多多",
            "sku": f"SKU-{i+1:05d}",
            "amount": paid_amount,
            "currency": "CNY",
            "ship_deadline": (order_time + timedelta(days=7)).isoformat(),
            "unit_price": str(paid_amount / max(1, random.randint(1, 5))),
            "item_amount": str(paid_amount),
            "image_url": "https://mock.example.com/product.jpg",
            "sku_text": f"规格{random.choice(['红', '绿', '蓝'])}",
        }
        orders.append(order)

    return orders


def generate_mock_products(
    tenant_id: int,
    store_id: str | None = None,
    count: int = 50
) -> list[dict[str, Any]]:
    """Generate mock PDD products for testing."""
    products = []
    categories = ["电子产品", "服装鞋帽", "食品饮料", "美妆护肤", "家居用品", "运动户外"]
    statuses = ["在售", "下架", "草稿", "违规下架"]

    for i in range(count):
        product = {
            "product_id": f"PDD{uuid.uuid4().hex[:12].upper()}",
            "product_key": f"product-{tenant_id}-{i+1}",
            "store_id": store_id or f"store-{tenant_id}-1",
            "product_name": f"测试商品_{categories[i % len(categories)]}_{i+1}",
            "category": categories[i % len(categories)],
            "price": round(random.uniform(10, 500), 2),
            "stock": random.randint(0, 1000),
            "sales": random.randint(0, 500),
            "status": statuses[i % len(statuses)],
            "sku": f"SKU-{i+1:05d}",
            "created_at": (datetime.now(SHANGHAI) - timedelta(days=random.randint(1, 90))).isoformat(),
            "updated_at": (datetime.now(SHANGHAI) - timedelta(days=random.randint(0, 7))).isoformat(),
        }
        products.append(product)

    return products


def generate_mock_compass(
    tenant_id: int,
    date_type: int = 1,
    store_id: str | None = None
) -> dict[str, Any]:
    """Generate mock PDD compass (经营罗盘) data for testing."""
    # 根据 date_type 确定标签
    date_labels = {
        1: "实时",
        20: "近1天",
        21: "近7天",
        23: "近30天",
    }
    label = date_labels.get(date_type, "实时")

    # 模拟核心指标
    base_amt = random.randint(10000, 100000)
    base_cnt = random.randint(100, 1000)

    compass = {
        "date_type": date_type,
        "date_label": label,
        "tenant_id": tenant_id,
        "store_id": store_id or f"store-{tenant_id}-1",
        "report_day": datetime.now(SHANGHAI).date().isoformat(),

        # 核心指标
        "pay_amount": base_amt,  # 销售额
        "pay_count": base_cnt,    # 成交单数
        "pay_user_count": round(base_cnt * 0.6),  # 成交人数
        "visit_count": round(base_amt / 10),  # 访客数
        "order_amount": base_amt * 0.95,  # 订单金额
        "refund_amount": round(base_amt * 0.05),  # 退款金额

        # 转化率
        "conversion_rate": round(random.uniform(0.01, 0.1), 4),  # 转化率
        "refund_rate": round(random.uniform(0.01, 0.1), 4),  # 退款率

        # 商品维度
        "product_count": random.randint(50, 200),  # 商品数
        "onsale_product_count": random.randint(30, 150),  # 在售商品数

        # 店铺评分
        "shop_score": round(random.uniform(4.5, 5.0), 2),  # 店铺评分
        "logistics_score": round(random.uniform(4.5, 5.0), 2),  # 物流评分
        "service_score": round(random.uniform(4.5, 5.0), 2),  # 服务评分

        # 流量数据
        "yesterday_visit": round(base_amt / 10 * random.uniform(0.8, 1.2)),
        "compare_yesterday_rate": round(random.uniform(-0.3, 0.5), 4),  # 环比

        # 源数据
        "source_url": "https://mms.pinduoduo.com/data/index.html",
        "synced_at": datetime.now(SHANGHAI).isoformat(),
    }

    return compass


def generate_mock_compass_data(tenant_id: int, store_id: str | None = None) -> dict[str, Any]:
    """Generate a complete mock compass snapshot with multiple date types."""
    compass_data = {}

    for date_type in [1, 20, 21, 23]:
        snapshot = generate_mock_compass(tenant_id, date_type, store_id)
        date_label = {1: "realtime", 20: "d1", 21: "d7", 23: "d30"}[date_type]
        compass_data[date_label] = snapshot

    return compass_data


# 便捷函数
def mock_orders_sync_data(
    tenant_id: int,
    date_window: str = "today",
    store_id: str | None = None
) -> tuple[list[dict[str, Any]], str]:
    """Mock data for orders sync."""
    orders = generate_mock_orders(tenant_id, date_window, store_id, count=20)
    return orders, f"https://mms.pinduoduo.com/od/index.html?window={date_window}"


def mock_products_sync_data(
    tenant_id: int,
    store_id: str | None = None
) -> tuple[list[dict[str, Any]], str]:
    """Mock data for products sync."""
    products = generate_mock_products(tenant_id, store_id, count=50)
    return products, "https://mms.pinduoduo.com/goods/goods_list.html"


def mock_compass_sync_data(
    tenant_id: int,
    date_type: int = 1,
    store_id: str | None = None
) -> tuple[dict[str, Any], str]:
    """Mock data for compass sync."""
    compass = generate_mock_compass(tenant_id, date_type, store_id)
    return compass, "https://mms.pinduoduo.com/data/index.html"
