"""Amazon LLM Agent chat entrypoint.

This module keeps the v1 safety contract intentionally strict: answers must
come from an allowed Amazon domain and from a real tool/source. If the local
tooling is not available yet, it returns an explicit no-data answer instead of
inventing operational facts.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime
import json
import os
import shutil
import subprocess
import time
from typing import Any

from app.amazon.report_crawler import crawl_amazon


ALLOWED_KEYWORDS = (
    "account health",
    "账户健康",
    "账号健康",
    "绩效",
    "order",
    "orders",
    "订单",
    "发货",
    "shipment",
    "inventory",
    "库存",
    "product",
    "products",
    "listing",
    "asin",
    "商品",
    "产品",
    "广告",
    "ads",
    "advertising",
    "message",
    "buyer message",
    "买家消息",
    "站内信",
    "review",
    "reviews",
    "评价",
    "评论",
    "差评",
    "case",
    "cases",
    "客服工单",
    "申诉",
)

WRITE_KEYWORDS = (
    "修改",
    "创建",
    "删除",
    "下架",
    "上架",
    "改价",
    "调价",
    "执行发货",
    "立即发货",
    "帮我发货",
    "退款",
    "回复买家",
    "发送回复",
    "帮我回复",
    "update",
    "create",
    "delete",
    "ship",
    "refund",
    "reply",
    "send",
    "write",
)

CROSS_PLATFORM_KEYWORDS = (
    "temu",
    "拼多多",
    "pdd",
    "抖音",
    "douyin",
    "1688",
    "淘宝",
    "taobao",
    "速卖通",
    "aliexpress",
)


@dataclass(frozen=True)
class BoundaryDecision:
    allowed: bool
    error_code: str = ""
    message: str = ""


def answer_amazon_chat(task: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    question = str(payload.get("message") or "").strip()
    store_name = str(payload.get("store_name") or "").strip()
    session_id = str(payload.get("session_id") or "").strip()

    decision = validate_boundary(question)
    captured_at = _now()
    if not decision.allowed:
        return {
            "status": "refused",
            "refused": True,
            "error_code": decision.error_code,
            "answer": decision.message,
            "source": {
                "type": "policy_boundary",
                "name": "amazon_chat_v1_scope",
                "captured_at": captured_at,
            },
            "captured_at": captured_at,
            "duration_ms": _elapsed_ms(started),
            "token_usage": {},
            "tool_calls": [],
            "session_id": session_id,
        }

    live = read_live_amazon_data(question=question, store_name=store_name, payload=payload)
    snapshot = payload.get("data_snapshot") if isinstance(payload.get("data_snapshot"), dict) else {}
    if live["ok"]:
        tool = {
            "tool_name": "amazon_ziniao_live_crawl",
            "ok": True,
            "args": live["args"],
            "summary": live["summary"],
            "duration_ms": live["duration_ms"],
            "source": live["source"],
        }
        answer = build_live_crawl_answer(question, store_name, live["data"], captured_at, live["scope"])
    elif snapshot_has_data(snapshot):
        tool = {
            "tool_name": "crosshub_local_amazon_tables",
            "ok": True,
            "args": {
                "store_name": store_name,
                "question_length": len(question),
                "platform_account_id": payload.get("platform_account_id", ""),
            },
            "summary": "使用 CrossHub 已同步 Amazon 本地数据快照",
            "duration_ms": 0,
            "source": {
                "type": "database_snapshot",
                "name": "crosshub_local_amazon_tables",
                "status": "ok",
                "captured_at": str(snapshot.get("captured_at") or captured_at),
            },
        }
        answer = build_snapshot_answer(question, store_name, snapshot, captured_at)
    else:
        tool = live if live.get("tool_name") else run_ziniao_chat_probe(question=question, store_name=store_name, payload=payload)
        answer = build_answer(question, store_name, captured_at, tool)
    return {
        "status": "success" if tool["ok"] else "no_live_data",
        "refused": False,
        "answer": answer,
        "source": tool["source"],
        "captured_at": captured_at,
        "duration_ms": _elapsed_ms(started),
        "token_usage": {},
        "tool_calls": [tool],
        "session_id": session_id,
    }


def validate_boundary(question: str) -> BoundaryDecision:
    text = question.lower()
    if not text.strip():
        return BoundaryDecision(False, "AMAZON_CHAT_EMPTY_MESSAGE", "请先输入要查询的 Amazon 运营问题。")
    if any(keyword in text for keyword in CROSS_PLATFORM_KEYWORDS):
        return BoundaryDecision(
            False,
            "AMAZON_CHAT_CROSS_PLATFORM_REFUSED",
            "这个通道只回答 Amazon 店铺问题。跨平台数据请切换到对应平台模块后再查询。",
        )
    if any(keyword in text for keyword in WRITE_KEYWORDS):
        return BoundaryDecision(
            False,
            "AMAZON_CHAT_WRITE_REFUSED",
            "Amazon AI 助手 v1 只做只读问答，不能执行修改、回复、发货、退款、删除等写操作。",
        )
    if not any(keyword in text for keyword in ALLOWED_KEYWORDS):
        return BoundaryDecision(
            False,
            "AMAZON_CHAT_SCOPE_REFUSED",
            "我只能回答 Amazon 账户健康、订单、商品/库存、广告、买家消息、评价和 Case 等经营问题。",
        )
    return BoundaryDecision(True)


def snapshot_has_data(snapshot: dict[str, Any]) -> bool:
    return any(
        isinstance(snapshot.get(key), list) and len(snapshot.get(key) or []) > 0
        for key in ("account_metrics", "operational_items", "top_products")
    )


def infer_amazon_scope(question: str) -> str:
    text = question.lower()
    if any(keyword in text for keyword in ("product", "products", "listing", "asin", "商品", "产品", "inventory", "库存", "广告", "ads", "acos")):
        return "reports"
    if any(keyword in text for keyword in ("order", "orders", "订单", "发货", "shipment", "message", "buyer message", "买家消息", "站内信", "review", "评价", "评论", "差评", "case", "客服工单", "申诉")):
        return "daily"
    return "account_health"


def read_live_amazon_data(*, question: str, store_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    browser_id = str(payload.get("browser_id") or payload.get("external_shop_id") or "").strip()
    browser_oauth = str(payload.get("browser_oauth") or "").strip()
    if not browser_id and not browser_oauth:
        return {
            "tool_name": "amazon_ziniao_live_crawl",
            "ok": False,
            "args": {"store_name": store_name, "question_length": len(question)},
            "summary": "当前店铺没有绑定紫鸟 browser_id/browser_oauth，无法直接打开紫鸟店铺浏览器",
            "duration_ms": _elapsed_ms(started),
            "source": {
                "type": "ziniao_binding",
                "name": "platform_account.ziniao_binding",
                "status": "missing",
                "captured_at": _now(),
            },
        }

    scope = infer_amazon_scope(question)
    try:
        timeout_seconds = float(os.environ.get("AMAZON_CHAT_CRAWL_TIMEOUT_SECONDS", "600"))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                crawl_amazon,
                scope=scope,
                browser_id=browser_id,
                browser_oauth=browser_oauth,
                store_name=store_name,
                merchant_id=str(payload.get("merchant_id") or "").strip(),
            )
            data = future.result(timeout=timeout_seconds)
        summary = data.get("result_summary") if isinstance(data, dict) else {}
        return {
            "tool_name": "amazon_ziniao_live_crawl",
            "ok": True,
            "scope": scope,
            "data": data if isinstance(data, dict) else {},
            "args": {
                "scope": scope,
                "store_name": store_name,
                "platform_account_id": payload.get("platform_account_id", ""),
                "question_length": len(question),
            },
            "summary": _trim(json.dumps(summary, ensure_ascii=False), 800),
            "duration_ms": _elapsed_ms(started),
            "source": {
                "type": "ziniao_webdriver",
                "name": f"ziniao_browser:{scope}",
                "status": "ok",
                "captured_at": _now(),
            },
        }
    except FutureTimeoutError:
        return {
            "tool_name": "amazon_ziniao_live_crawl",
            "ok": False,
            "scope": scope,
            "args": {
                "scope": scope,
                "store_name": store_name,
                "platform_account_id": payload.get("platform_account_id", ""),
                "question_length": len(question),
            },
            "summary": "紫鸟实时读取超时",
            "duration_ms": _elapsed_ms(started),
            "source": {
                "type": "ziniao_webdriver",
                "name": f"ziniao_browser:{scope}",
                "status": "timeout",
                "captured_at": _now(),
            },
        }
    except Exception as exc:
        return {
            "tool_name": "amazon_ziniao_live_crawl",
            "ok": False,
            "scope": scope,
            "args": {
                "scope": scope,
                "store_name": store_name,
                "platform_account_id": payload.get("platform_account_id", ""),
                "question_length": len(question),
            },
            "summary": str(exc),
            "duration_ms": _elapsed_ms(started),
            "source": {
                "type": "ziniao_webdriver",
                "name": f"ziniao_browser:{scope}",
                "status": "failed",
                "captured_at": _now(),
            },
        }


def build_live_crawl_answer(question: str, store_name: str, data: dict[str, Any], captured_at: str, scope: str) -> str:
    del question
    lines = [f"已通过紫鸟绑定浏览器读取 {store_name or '当前店铺'} 的 Amazon 实时数据。"]
    summary = data.get("result_summary") if isinstance(data.get("result_summary"), dict) else {}
    metrics = list(data.get("metrics") or [])
    products = list(data.get("products") or [])
    orders = list(data.get("outbound_orders") or [])
    messages = list(data.get("buyer_messages") or [])
    reviews = list(data.get("reviews") or [])
    cases = list(data.get("cases") or [])

    if metrics:
        abnormal = [
            row for row in metrics
            if str(row.get("status") or "").lower() not in ("", "normal", "ok", "healthy")
        ]
        lines.append("账户健康：")
        for row in (abnormal or metrics)[:5]:
            lines.append(f"- {row.get('label') or row.get('metric_label') or row.get('metric_key')}: {row.get('value') or row.get('value_text') or '-'}，状态 {row.get('status') or '-'}")
    if orders:
        lines.append("订单/发货：")
        for row in orders[:5]:
            lines.append(f"- {row.get('order_no') or row.get('shipment_id') or row.get('id')}: {row.get('status') or '-'}")
    if products:
        lines.append("产品/库存/广告：")
        for row in products[:5]:
            lines.append(
                f"- {row.get('product_name') or row.get('asin') or row.get('sku')}: "
                f"30日订单 {row.get('orders_30d') or 0}，库存 {row.get('inventory') or 0}，ACOS {row.get('acos') or 0}"
            )
    if messages or reviews or cases:
        lines.append("消息/评价/Case：")
        for row in messages[:3]:
            lines.append(f"- 消息 {row.get('subject') or row.get('order_no') or row.get('id')}: {row.get('status') or '-'}")
        for row in reviews[:3]:
            lines.append(f"- 评价 {row.get('asin') or row.get('order_no') or row.get('id')}: {row.get('rating') or '-'} 星，{row.get('status') or '-'}")
        for row in cases[:3]:
            lines.append(f"- Case {row.get('case_id') or row.get('subject') or row.get('id')}: {row.get('status') or '-'}")
    if len(lines) == 1:
        lines.append("已完成读取，但当前页面没有解析到可展示的明细。")
    if summary:
        lines.append(
            f"\n解析摘要：产品 {summary.get('products_count', 0)}，订单 {summary.get('orders_count', 0)}"
        )
    lines.append(f"数据来源：紫鸟绑定店铺浏览器 / Amazon Seller Central（scope={scope}）")
    lines.append(f"采集时间：{captured_at}")
    return "\n".join(lines)


def build_snapshot_answer(question: str, store_name: str, snapshot: dict[str, Any], captured_at: str) -> str:
    text = question.lower()
    lines = [f"基于 {store_name or '当前店铺'} 已同步的 Amazon 数据快照："]

    if any(keyword in text for keyword in ("account health", "账户健康", "账号健康", "绩效")):
        metrics = list(snapshot.get("account_metrics") or [])
        risks = [
            row for row in metrics
            if str(row.get("status") or "").lower() not in ("", "normal", "ok", "healthy")
        ]
        if risks:
            lines.append("账户健康关注项：")
            for row in risks[:5]:
                lines.append(
                    f"- {row.get('metric_label') or row.get('metric_key')}: "
                    f"{row.get('value_text') or '-'}，状态 {row.get('status') or '-'}"
                )
        elif metrics:
            lines.append("账户健康指标未发现非正常状态。")

    if any(keyword in text for keyword in ("order", "orders", "订单", "发货", "shipment")):
        items = list(snapshot.get("operational_items") or [])
        order_items = [
            parse_operational_item(row) for row in items
            if str(row.get("item_type") or "").lower() in ("outbound", "order", "shipment")
        ]
        if order_items:
            lines.append("订单/发货待关注事项：")
            for row in order_items[:5]:
                title = row.get("order_no") or row.get("shipment_id") or row.get("external_key") or row.get("subject") or "未命名事项"
                status = row.get("status") or row.get("alert_level") or "-"
                lines.append(f"- {title}: {status}")

    if any(keyword in text for keyword in ("product", "products", "listing", "asin", "商品", "产品", "inventory", "库存", "广告", "ads", "acos")):
        products = list(snapshot.get("top_products") or [])
        if products:
            lines.append("产品/库存/广告 TOP 数据：")
            for row in products[:5]:
                name = row.get("product_name") or row.get("asin") or row.get("sku") or "未命名产品"
                lines.append(
                    f"- {name}: 30日订单 {row.get('orders_30d') or 0}，"
                    f"库存 {row.get('inventory') or 0}，ACOS {row.get('acos') or 0}"
                )

    if any(keyword in text for keyword in ("message", "buyer message", "买家消息", "站内信", "review", "reviews", "评价", "评论", "差评", "case", "cases", "客服工单", "申诉")):
        items = list(snapshot.get("operational_items") or [])
        feedback_items = [
            parse_operational_item(row) for row in items
            if str(row.get("item_type") or "").lower() in ("message", "buyer_message", "review", "case", "seller_news")
        ]
        if feedback_items:
            lines.append("消息/评价/Case 待关注事项：")
            for row in feedback_items[:5]:
                title = row.get("subject") or row.get("order_no") or row.get("external_key") or row.get("asin") or "未命名事项"
                status = row.get("status") or row.get("rating") or row.get("alert_level") or "-"
                lines.append(f"- {title}: {status}")

    if len(lines) == 1:
        lines.append("当前问题属于允许范围，但现有快照里没有匹配到足够细分的数据。")
    lines.append(f"\n数据来源：CrossHub Amazon 已同步本地表")
    lines.append(f"采集时间：{snapshot.get('captured_at') or captured_at}")
    return "\n".join(lines)


def parse_operational_item(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload_json")
    parsed: dict[str, Any] = {}
    if isinstance(payload, str) and payload.strip():
        try:
            raw = json.loads(payload)
            if isinstance(raw, dict):
                parsed.update(raw)
        except Exception:
            pass
    parsed.setdefault("external_key", row.get("external_key"))
    parsed.setdefault("synced_at", row.get("synced_at"))
    return parsed


def run_ziniao_chat_probe(*, question: str, store_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    cli = os.environ.get("ZINIAO_CLI_BIN", "ziniao-cli").strip() or "ziniao-cli"
    executable = shutil.which(cli)
    if not executable:
        return {
            "tool_name": "ziniao_cli",
            "ok": False,
            "args": {
                "store_name": store_name,
                "question_length": len(question),
                "platform_account_id": payload.get("platform_account_id", ""),
            },
            "summary": "未检测到紫鸟 CLI，未获取实时页面数据",
            "duration_ms": _elapsed_ms(started),
            "source": {
                "type": "local_tool",
                "name": "ziniao_cli",
                "status": "missing",
                "captured_at": _now(),
            },
        }

    try:
        completed = subprocess.run(
            [executable, "doctor"],
            check=False,
            capture_output=True,
            text=True,
            timeout=float(os.environ.get("AMAZON_CHAT_TOOL_TIMEOUT_SECONDS", "20")),
        )
    except Exception as exc:
        return {
            "tool_name": "ziniao_cli",
            "ok": False,
            "args": {"store_name": store_name, "question_length": len(question)},
            "summary": str(exc),
            "duration_ms": _elapsed_ms(started),
            "source": {
                "type": "local_tool",
                "name": "ziniao_cli",
                "status": "failed",
                "captured_at": _now(),
            },
        }

    output = (completed.stdout or completed.stderr or "").strip()
    return {
        "tool_name": "ziniao_cli",
        "ok": completed.returncode == 0,
        "args": {"store_name": store_name, "question_length": len(question)},
        "summary": _trim(output, 600),
        "duration_ms": _elapsed_ms(started),
        "source": {
            "type": "local_tool",
            "name": "ziniao_cli doctor",
            "status": "ok" if completed.returncode == 0 else "failed",
            "captured_at": _now(),
        },
    }


def build_answer(question: str, store_name: str, captured_at: str, tool: dict[str, Any]) -> str:
    if not tool.get("ok"):
        return (
            f"已收到 {store_name or '当前店铺'} 的问题：{question}\n\n"
            "当前本机未取得 Amazon 实时页面数据，因此我不会生成经营结论或数字判断。\n\n"
            f"数据来源：{tool.get('summary') or '未获取到实时页面数据'}\n"
            f"采集时间：{captured_at}\n\n"
            "请先确认本机 Sync Helper 在线，并配置可用的紫鸟 CLI/后续 LLM 工具通道后再重试。"
        )
    return (
        f"已连接本机紫鸟工具，但 v1 还没有可执行的 Amazon 读数工具映射，暂不生成业务结论。\n\n"
        f"店铺：{store_name or '当前店铺'}\n"
        f"数据来源：{tool.get('source', {}).get('name', 'ziniao_cli')}\n"
        f"采集时间：{captured_at}\n"
        f"工具状态：{tool.get('summary') or '可用'}"
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _trim(value: str, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[:limit] + "..."
