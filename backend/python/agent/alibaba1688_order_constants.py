"""Frozen 1688 consumer-order XHR constants. Filled from Day0 probes 2026-08-19."""
from __future__ import annotations

# Live order sync enabled after the Day0 attachment fields were completed:
# docs/superpowers/specs/attachments/1688-consumer-orders-xhr.md
ORDERS_XHR_READY = True

ORDER_LIST_API = "mtop.1688.trading.dataline.service"
ORDER_LIST_SERVICE_ID = "OrderListDataLineService.sellerOrderList"
ORDER_LIST_PAGE_SIZE = 10  # platform caps pageSize at 10

REFUND_LIST_API = "mtop.1688.dw.refund.list"

TRADE_STATUS_MAP = {
    "waitbuyerpay": "unpaid",
    "waitsellersend": "paid",
    "waitbuyerreceive": "paid",
    "confirm_goods_but_not_fund": "paid",
    "waitselleragree": "refunding",
    "aftersale": "after_sale",
    "toushu": "dispute",
    "availableRemark": "completed",
    "success": "completed",
    "cancel": "cancelled",
}

# 已支付状态集合：销售额只统计这些状态（或 gmtPayment 非空）。
PAID_STATUSES = frozenset(
    {"waitsellersend", "waitbuyerreceive", "confirm_goods_but_not_fund", "availableRemark", "success"}
)


def assert_orders_xhr_ready() -> None:
    if not ORDERS_XHR_READY or not ORDER_LIST_API or not ORDER_LIST_SERVICE_ID:
        raise RuntimeError("A1688_ORDERS_NEED_DAY0: 1688 消费者订单 XHR 未完成 Day0，禁止 live 同步")
