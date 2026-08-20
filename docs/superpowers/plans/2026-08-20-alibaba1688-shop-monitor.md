# 1688 竞店实时监控模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有通用竞店监控框架上新增 1688 平台适配器，实现三家 1688 店铺的爆款 Top N + 指定商品盯梢、1–2 小时定时快照、日增量估算与六类告警。

**Architecture:** 复用 `monitor_target/schedule/job/snapshot/signal` 通用框架；新增 Python 采集器与 `MonitorPlatformAdapter` 适配器（使用已有 1688 登录会话与 `mtop` 接口），新增排程入队器消费 `next_run_at`；Java 侧补 1688 URL 校验、趋势/信号/最新商品接口；前端在 1688 模块加“竞店监控”Tab。

**Tech Stack:** Python 3.11 + Playwright 1.60 + SQLite（`backend/data/crosshub.db`）；Spring Boot（Maven）；Vue 3 + Element Plus + ECharts；pytest / JUnit 5。

## Global Constraints

- 所有 Python 单测在 `backend/python` 下执行：`python -m pytest tests/<file> -q`。
- Java 测试在 `backend/java` 下执行：`mvn -q -Dtest=<TestClass> test`。
- 前端构建在 `dev/vue-site` 下执行：`npm run build`。
- 数据库为共享 SQLite `backend/data/crosshub.db`；迁移必须幂等（`PRAGMA table_info` 判断列是否存在）。
- 时间统一 Asia/Shanghai，快照时间格式 `YYYY-MM-DD HH:mm:ss`。
- 1688 浏览器 profile 单飞：采集任务与现有 agent 1688 任务不得并发占用同一 profile。
- 新增列全部可空或带默认值，不破坏现有 Temu 监控。
- 每个任务独立可测、独立提交，提交信息用 conventional commits。

## File Structure

| 文件 | 动作 | 职责 |
|------|------|------|
| `backend/python/app/platforms/alibaba1688_monitor_utils.py` | 新增 | 纯函数：URL 规范化、销量文案解析、价格解析 |
| `backend/python/app/platforms/alibaba1688_monitor_parse.py` | 新增 | 纯函数：店铺列表/详情/shopcard 响应解析 |
| `backend/python/app/platforms/alibaba1688_shop_collector.py` | 新增 | 浏览器采集：开店铺页、拉 Top N、补全详情 |
| `backend/python/app/platforms/alibaba1688_monitor_adapter.py` | 新增 | `MonitorPlatformAdapter` 实现 |
| `backend/python/app/monitor_schedule_enqueuer.py` | 新增 | 排程入队器 |
| `backend/python/app/monitor_db.py` | 修改 | 结果 schema 增加 1688 列（新库） |
| `backend/python/app/monitor_worker_service.py` | 修改 | 日增量计算 + 新信号检测 + persist 扩展 |
| `backend/python/monitor_worker.py` | 修改 | 注册 1688 适配器 + 调用排程入队器 |
| `backend/python/tests/test_alibaba1688_monitor_*.py` | 新增 | 上述模块单测 |
| `backend/python/tests/fixtures/alibaba1688_monitor/*.json` | 已生成 | 真实接口响应 fixtures |
| `scripts/_smoke_1688_monitor.py` | 新增 | 三家真实店铺冒烟脚本 |
| `backend/java/.../config/migration/V45Alibaba1688MonitorMigration.java` | 新增 | 表结构迁移 |
| `backend/java/.../monitor/util/Alibaba1688MonitorUrlValidator.java` | 新增 | 1688 URL 校验/规范化 |
| `backend/java/.../monitor/service/MonitorService.java` | 修改 | 新增 trend/signals 接口 |
| `backend/java/.../monitor/service/impl/MonitorServiceImpl.java` | 修改 | URL 平台分发、getLatest 返回商品、trend/signals 实现 |
| `backend/java/.../monitor/controller/MonitorController.java` | 修改 | 新增 trend/signals 路由 |
| `backend/java/.../test/.../Alibaba1688MonitorUrlValidatorTest.java` | 新增 | 校验器单测 |
| `dev/vue-site/src/api/alibaba1688MonitorApi.js` | 新增 | 前端 API 层 |
| `dev/vue-site/src/components/alibaba1688/Alibaba1688MonitorPanel.vue` | 新增 | 竞店监控面板 |
| `dev/vue-site/src/views/alibaba1688/Alibaba1688ModuleView.vue` | 修改 | 新增“竞店监控”Tab |

---

### Task 1: 1688 监控工具函数（纯函数）

**Files:**
- Create: `backend/python/app/platforms/alibaba1688_monitor_utils.py`
- Test: `backend/python/tests/test_alibaba1688_monitor_utils.py`

**Interfaces:**
- Consumes: 无
- Produces: `canonicalize_shop_url(url: str) -> str`、`offer_id_from_url(url: str) -> str`、`canonicalize_offer_url(url: str) -> str`、`parse_sales_text(text: str | None) -> int`、`parse_price(text: str | None) -> float`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from app.platforms.alibaba1688_monitor_utils import (
    canonicalize_offer_url,
    canonicalize_shop_url,
    offer_id_from_url,
    parse_price,
    parse_sales_text,
)


class Alibaba1688MonitorUtilsTest(unittest.TestCase):
    def test_canonicalize_shop_url(self):
        self.assertEqual(
            canonicalize_shop_url("https://shop16yx1905b2433.1688.com"),
            "https://shop16yx1905b2433.1688.com",
        )
        self.assertEqual(
            canonicalize_shop_url("shop16yx1905b2433.1688.com"),
            "https://shop16yx1905b2433.1688.com",
        )
        with self.assertRaises(ValueError):
            canonicalize_shop_url("https://detail.1688.com/offer/930671411701.html")

    def test_offer_url_helpers(self):
        self.assertEqual(
            offer_id_from_url("https://detail.1688.com/offer/930671411701.html"),
            "930671411701",
        )
        self.assertEqual(
            canonicalize_offer_url("https://m.1688.com/offer/930671411701.html"),
            "https://detail.1688.com/offer/930671411701.html",
        )
        with self.assertRaises(ValueError):
            canonicalize_offer_url("https://shop16yx1905b2433.1688.com")

    def test_parse_sales_text(self):
        self.assertEqual(parse_sales_text("已售10+件"), 10)
        self.assertEqual(parse_sales_text("已售10万+件"), 100000)
        self.assertEqual(parse_sales_text("成交246,920件"), 246920)
        self.assertEqual(parse_sales_text(""), 0)

    def test_parse_price(self):
        self.assertEqual(parse_price("¥7.8"), 7.8)
        self.assertEqual(parse_price(""), 0.0)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_alibaba1688_monitor_utils.py -q`
Expected: FAIL（ModuleNotFoundError: alibaba1688_monitor_utils）

- [ ] **Step 3: 最小实现**

```python
"""Pure helpers for 1688 shop monitoring (no browser/DB dependencies)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_SHOP_HOST = re.compile(r"^shop\d+\.1688\.com$", re.IGNORECASE)
_OFFER_ID_RE = re.compile(r"/offer/(\d+)\.html", re.IGNORECASE)


def canonicalize_shop_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        raise ValueError("empty 1688 shop url")
    parsed = urlparse(text if "://" in text else "https://" + text)
    host = (parsed.hostname or "").lower()
    if not _SHOP_HOST.match(host):
        raise ValueError(f"not a 1688 shop url: {url}")
    return f"https://{host}"


def offer_id_from_url(url: str) -> str:
    m = _OFFER_ID_RE.search(str(url or ""))
    return m.group(1) if m else ""


def canonicalize_offer_url(url: str) -> str:
    oid = offer_id_from_url(url)
    if not oid:
        raise ValueError(f"not a 1688 offer url: {url}")
    return f"https://detail.1688.com/offer/{oid}.html"


def parse_sales_text(text: str | None) -> int:
    raw = str(text or "").replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万)?\+?\s*件", raw)
    if not m:
        return 0
    num = float(m.group(1))
    if m.lastindex and m.group(2):
        num *= 10000
    return int(num)


def parse_price(text: str | None) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)", str(text or ""))
    return float(m.group(1)) if m else 0.0
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_alibaba1688_monitor_utils.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/python/app/platforms/alibaba1688_monitor_utils.py backend/python/tests/test_alibaba1688_monitor_utils.py
git commit -m "feat(1688-monitor): url and sales-text parsing utils"
```

### Task 2: 店铺列表 / 详情 / shopcard 响应解析（纯函数）

**Files:**
- Create: `backend/python/app/platforms/alibaba1688_monitor_parse.py`
- Test: `backend/python/tests/test_alibaba1688_monitor_parse.py`
- Fixtures（已存在，勿删）: `backend/python/tests/fixtures/alibaba1688_monitor/{moduledata_3,moduledata_4,shopcard_5,mmga_9,mmga_17}.json`

**Interfaces:**
- Consumes: Task 1 的 `parse_sales_text`
- Produces: `unwrap_jsonp(text) -> str`、`parse_shop_list_response(text) -> {"member_id": str, "offers": list, "total_count": str}`、`parse_list_item(item, *, rank) -> dict`、`parse_shopcard_response(text) -> dict`、`parse_offer_detail_responses(texts: list[str]) -> dict`

- [ ] **Step 1: 写失败测试**

```python
import json
import unittest
from pathlib import Path

from app.platforms.alibaba1688_monitor_parse import (
    parse_offer_detail_responses,
    parse_shop_list_response,
    parse_shopcard_response,
)

FIXTURES = Path(__file__).parent / "fixtures" / "alibaba1688_monitor"


class Alibaba1688MonitorParseTest(unittest.TestCase):
    def _load(self, name):
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_parse_shop_list_tradenumdown(self):
        result = parse_shop_list_response(self._load("moduledata_4.json"))
        self.assertEqual(result["member_id"], "b2b-221111714406302508")
        self.assertGreaterEqual(len(result["offers"]), 10)
        first = result["offers"][0]
        self.assertEqual(first["offer_id"], "824828511612")
        self.assertEqual(first["rank"], 1)
        self.assertEqual(first["total_sales"], 100000)  # vagueSaleQuantity "10万+"
        self.assertTrue(first["listed_at"])
        self.assertTrue(first["url"].startswith("https://"))

    def test_parse_shop_list_skips_non_tradenumdown(self):
        result = parse_shop_list_response(self._load("moduledata_3.json"))
        self.assertEqual(result["offers"], [])  # wangpu_score list is not the bestseller source

    def test_parse_shopcard(self):
        shop = parse_shopcard_response(self._load("shopcard_5.json"))
        self.assertEqual(shop["shop_name"], "深圳市东博瑞户外用品有限公司")
        self.assertEqual(shop["shop_fans"], 722)
        self.assertEqual(shop["shop_return_rate"], "73%")
        self.assertEqual(shop["category"], "垂钓用品")

    def test_parse_offer_detail(self):
        detail = parse_offer_detail_responses(
            [self._load("mmga_9.json"), self._load("mmga_17.json")]
        )
        self.assertIsNotNone(detail["current"])
        self.assertEqual(detail["current"]["offerId"], 930671411701)
        advise = {str(x.get("key")): str(x.get("value")) for x in (detail["advise"] or [])}
        self.assertIn("orderCnt30d", advise)
        self.assertIn("dfPoint", advise)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_alibaba1688_monitor_parse.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 最小实现**

```python
"""Pure parsers for 1688 shop monitor responses (no browser/DB)."""
from __future__ import annotations

import json
import re
from typing import Any

from app.platforms.alibaba1688_monitor_utils import parse_sales_text


def unwrap_jsonp(text: str) -> str:
    body = str(text or "").strip()
    if body.startswith("mtopjsonp"):
        start = body.find("(")
        end = body.rfind(")")
        if start >= 0 and end > start:
            body = body[start + 1 : end]
    return body


def _json(text: str) -> dict[str, Any]:
    return json.loads(unwrap_jsonp(text))


def parse_shop_list_response(text: str) -> dict[str, Any]:
    payload = _json(text)
    data = payload.get("data") or {}
    appdata = data.get("appdata") or {}
    member_id = str(appdata.get("memberId") or "")
    offers: list[dict[str, Any]] = []
    if str(appdata.get("sortType")) == "tradenumdown":
        for idx, item in enumerate(data.get("offerModuleList") or [], start=1):
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id") or "")
            if not oid or oid == "0":
                continue
            offers.append(parse_list_item(item, rank=idx))
    return {
        "member_id": member_id,
        "offers": offers,
        "total_count": str(data.get("totalCount") or ""),
    }


def parse_list_item(item: dict, *, rank: int) -> dict[str, Any]:
    vague = str(item.get("vagueSaleQuantity") or "")
    rebuy = ""
    for p in item.get("offerPointModelList") or []:
        if isinstance(p, dict) and "复购" in str(p.get("pointText") or ""):
            rebuy = str(p.get("pointText") or "")
            break
    url = str(item.get("offerDetailUrl") or "")
    if url.startswith("//"):
        url = "https:" + url
    return {
        "offer_id": str(item.get("id") or ""),
        "title": str(item.get("subject") or ""),
        "price": str(item.get("offerPrice") or ""),
        "sale_text": vague,
        "total_sales": parse_sales_text(vague),
        "rank": rank,
        "listed_at": str(item.get("gmtCreate") or "")[:10],
        "url": url,
        "image_url": _first_image(item.get("offerImages")),
        "status": str(item.get("status") or ""),
        "expired": str(item.get("expired") or "").lower() == "true",
        "rebuy_rate": rebuy,
        "raw_json": json.dumps(item, ensure_ascii=False),
    }


def parse_shopcard_response(text: str) -> dict[str, Any]:
    payload = _json(text)
    model = (payload.get("data") or {}).get("model") or {}
    if not model.get("shopName"):
        return {}
    fans = 0
    fav = str(((model.get("shopButton") or {}).get("fuzzyFavCount")) or "")
    m = re.search(r"([\d.]+)\s*([kK万])?", fav)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit and unit.lower() == "k":
            num *= 1000
        elif unit == "万":
            num *= 10000
        fans = int(num)
    shop_data = {}
    for sd in model.get("shopData") or []:
        if isinstance(sd, dict):
            shop_data[str(sd.get("dataKey") or "")] = str(sd.get("dataValue") or "")
    return {
        "shop_name": str(model.get("shopName") or ""),
        "shop_url": str(model.get("shopUrl") or ""),
        "shop_fans": fans,
        "quality_rate": str(model.get("qualitySatisfactionRate") or ""),
        "shop_return_rate": shop_data.get("店铺回头率", ""),
        "delivery_48h_rate": shop_data.get("48小时支揽率", ""),
        "category": str(model.get("mainCategoryName") or ""),
    }


def parse_offer_detail_responses(texts: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"current": None, "attrs_json": "", "advise": None, "rebuy_rate": ""}
    for text in texts:
        try:
            payload = _json(text)
        except Exception:
            continue
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("currentOffer"), dict):
            out["current"] = data["currentOffer"]
        inner = data.get("data")
        if not isinstance(inner, dict):
            continue
        if isinstance(inner.get("offerDecisionAttrs"), list):
            out["attrs_json"] = json.dumps(inner["offerDecisionAttrs"], ensure_ascii=False)
        deeper = inner.get("data")
        if isinstance(deeper, dict) and isinstance(deeper.get("adviseList"), list):
            out["advise"] = deeper["adviseList"]
        elif isinstance(deeper, list):
            for item in deeper:
                if isinstance(item, dict) and "复购" in str(item.get("text") or ""):
                    out["rebuy_rate"] = str(item.get("text") or "")
    return out


def _first_image(value: Any) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("originalImageUrl") or first.get("imageUrl") or "")
        return str(first)
    return ""
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_alibaba1688_monitor_parse.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/python/app/platforms/alibaba1688_monitor_parse.py backend/python/tests/test_alibaba1688_monitor_parse.py
git commit -m "feat(1688-monitor): parse shop list, shopcard and offer detail responses"
```

### Task 3: 浏览器采集器（crawl_shop）与真实店铺冒烟

**Files:**
- Create: `backend/python/app/platforms/alibaba1688_shop_collector.py`
- Create: `scripts/_smoke_1688_monitor.py`

**Interfaces:**
- Consumes: Task 1/2 解析函数；`agent.alibaba1688_tasks._launch/_close/_looks_logged_in`；租户 5 已登录 profile
- Produces: `crawl_shop(*, tenant_id: int, target: dict, max_products: int) -> {"platform": "1688", "snapshot_at": str, "products": list[dict], "shop": dict, "meta": dict}`；product 字段：`offer_id/title/price/price_range/sale_text/total_sales/rank/listed_at/url/image_url/status/expired/rebuy_rate/shop_name/shop_url/shop_fans/quality_rate/shop_return_rate/dropship_7d/dropship_30d/dropship_heat/attrs_json/is_pinned/raw_json`

- [ ] **Step 1: 实现采集器**

```python
"""1688 shop collector: bestseller list + offer details via the logged-in session."""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.platforms.alibaba1688_monitor_parse import (
    parse_offer_detail_responses,
    parse_shop_list_response,
    parse_shopcard_response,
)
from app.platforms.alibaba1688_monitor_utils import (
    canonicalize_offer_url,
    canonicalize_shop_url,
    offer_id_from_url,
    parse_sales_text,
)

PROFILE_LOCK = threading.Lock()

_MODULEDATA_API = "mtop.alisite.cbu.winport.sync.moduledata.get"
_MMGA_API = "mtop.1688.mmga.offerdetail.service"
_SHOPCARD_API = "mtop.1688.moga.pc.shopcard"


def crawl_shop(*, tenant_id: int, target: dict, max_products: int) -> dict[str, Any]:
    config = _target_config(target)
    pinned = [str(x) for x in (config.get("pinned_offer_ids") or [])]
    top_n = max(1, min(int(config.get("top_n") or max_products or 20), int(max_products or 20)))
    raw_url = str(target.get("target_url") or "")
    strategy = str(target.get("crawl_strategy") or "1688_shop_topn")

    if strategy == "1688_pinned_offers":
        oid = offer_id_from_url(raw_url)
        if not oid:
            raise ValueError(f"not a 1688 offer url: {raw_url}")
        shop_url = ""
        offers = [_empty_offer(oid, canonicalize_offer_url(raw_url))]
        shop: dict[str, Any] = {}
    else:
        shop_url = canonicalize_shop_url(raw_url)
        offers: list[dict[str, Any]] = []
        shop = {}

    with PROFILE_LOCK:
        from agent.alibaba1688_tasks import _close, _launch, _looks_logged_in

        pw = context = page = None
        try:
            pw, context, page = _launch(tenant_id, headless=True, goto="https://work.1688.com/")
            if not _looks_logged_in(page, context):
                raise RuntimeError("MONITOR_AUTH_REQUIRED: 1688 未登录或登录已失效")
            page.wait_for_timeout(4000)
            if shop_url:
                shop, offers = _fetch_shop_offers(page, shop_url, top_n)
            rows = _fetch_offer_details(page, offers, pinned)
        finally:
            _close(pw, context)

    rows.sort(key=lambda r: (r.get("is_pinned") == 0, r.get("rank") or 999))
    return {
        "platform": "1688",
        "snapshot_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "products": rows,
        "shop": shop,
        "meta": {"member_id": shop.get("member_id", ""), "top_n": top_n, "pinned": pinned},
    }


def _target_config(target: dict) -> dict[str, Any]:
    raw = target.get("config_json") or "{}"
    try:
        return json.loads(str(raw))
    except Exception:
        return {}


def _empty_offer(oid: str, url: str) -> dict[str, Any]:
    return {
        "offer_id": oid,
        "title": "",
        "price": "",
        "sale_text": "",
        "total_sales": 0,
        "rank": 0,
        "listed_at": "",
        "url": url,
        "image_url": "",
        "status": "",
        "expired": False,
        "rebuy_rate": "",
        "raw_json": "",
    }


def _fetch_shop_offers(page, shop_url: str, top_n: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    captured: list[str] = []

    def on_response(resp) -> None:
        try:
            if _MODULEDATA_API in str(resp.url or ""):
                text = resp.text()
                if text:
                    captured.append(text)
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(shop_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(8000)
        _assert_no_risk(page)
    finally:
        page.remove_listener("response", on_response)

    member_id = ""
    offers: dict[str, dict[str, Any]] = {}
    for text in captured:
        parsed = parse_shop_list_response(text)
        if parsed["member_id"]:
            member_id = parsed["member_id"]
        for item in parsed["offers"]:
            offers[str(item["offer_id"])] = item
    if not member_id:
        raise RuntimeError("MONITOR_PARSE_FAILED: 店铺页未返回 memberId")
    if not offers:
        raise RuntimeError("MONITOR_NO_PRODUCTS: 店铺页未返回商品列表")
    ordered = sorted(offers.values(), key=lambda x: int(x.get("rank") or 999))[:top_n]
    return {"member_id": member_id, "shop_url": shop_url}, ordered


def _fetch_offer_details(page, offers: list[dict[str, Any]], pinned: list[str]) -> list[dict[str, Any]]:
    rows = {str(o["offer_id"]): dict(o) for o in offers}
    for oid in pinned:
        if oid not in rows:
            rows[oid] = _empty_offer(oid, f"https://detail.1688.com/offer/{oid}.html")
    out: list[dict[str, Any]] = []
    for oid in list(rows):
        captured: list[str] = []

        def on_response(resp) -> None:
            try:
                url = str(resp.url or "")
                if _MMGA_API in url or _SHOPCARD_API in url:
                    text = resp.text()
                    if text:
                        captured.append(text)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            page.goto(f"https://detail.1688.com/offer/{oid}.html", wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(4000)
            _assert_no_risk(page)
        finally:
            page.remove_listener("response", on_response)

        row = rows[oid]
        try:
            detail = parse_offer_detail_responses(captured)
            shop = {}
            for text in captured:
                candidate = parse_shopcard_response(text)
                if candidate.get("shop_name"):
                    shop = candidate
                    break
            row = _merge_detail(row, detail, shop)
        except Exception:
            # 单商品失败不阻断整店：保留列表已有字段，继续下一个
            pass
        row["is_pinned"] = 1 if oid in pinned else 0
        out.append(row)
        time.sleep(0.8)
    return out


def _assert_no_risk(page) -> None:
    try:
        url = str(page.url or "")
        if "punish" in url or "_____tmd_____" in url:
            raise RuntimeError("MONITOR_RISK_BLOCKED: 1688 风控验证页（punish/captcha），已退避")
        content = page.content()[:3000]
        if "rgv587_flag" in content or "验证码" in content or "captcha" in content.lower():
            raise RuntimeError("MONITOR_RISK_BLOCKED: 1688 风控验证页（punish/captcha），已退避")
    except RuntimeError:
        raise
    except Exception:
        pass


def _merge_detail(row: dict[str, Any], detail: dict[str, Any], shop: dict[str, Any]) -> dict[str, Any]:
    cur = detail.get("current") or {}
    if cur:
        if not row.get("title"):
            row["title"] = str(cur.get("title") or "")
        if not row.get("price"):
            row["price"] = str(cur.get("price") or "")
        if not row.get("sale_text"):
            row["sale_text"] = str(cur.get("saleText") or "")
        row["total_sales"] = max(
            int(row.get("total_sales") or 0),
            parse_sales_text(cur.get("saleText")),
        )
    if detail.get("attrs_json"):
        row["attrs_json"] = detail["attrs_json"]
    if detail.get("rebuy_rate"):
        row["rebuy_rate"] = detail["rebuy_rate"]
    for item in detail.get("advise") or []:
        key = str(item.get("key") or "")
        value = str(item.get("value") or "")
        if key == "dfPoint":
            try:
                row["dropship_heat"] = int(float(value))
            except ValueError:
                pass
        elif key == "orderCnt30d":
            row["dropship_30d"] = value
        elif key == "orderCnt7d":
            row["dropship_7d"] = value
        elif key == "offerPublishDate" and not row.get("listed_at"):
            row["listed_at"] = value
    if shop.get("shop_name"):
        for key in ("shop_name", "shop_url", "shop_fans", "quality_rate", "shop_return_rate", "delivery_48h_rate", "category"):
            if shop.get(key):
                row.setdefault(key, shop[key])
    row["raw_json"] = json.dumps(
        {
            "current": cur,
            "attrs": detail.get("attrs_json"),
            "advise": detail.get("advise"),
            "shop": {k: shop.get(k) for k in ("shop_name", "shop_url", "quality_rate", "shop_return_rate", "delivery_48h_rate", "category", "shop_fans")},
        },
        ensure_ascii=False,
    )
    return row
```

- [ ] **Step 2: 写冒烟脚本**

```python
"""Smoke: collect the three seed 1688 shops once and print a summary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "python"))

from app.platforms.alibaba1688_shop_collector import crawl_shop  # noqa: E402

SEEDS = [
    {"label": "寻渔记", "url": "https://shop17682i6w5i484.1688.com", "pinned": ["867473865842"]},
    {"label": "东博瑞", "url": "https://shop16yx1905b2433.1688.com", "pinned": ["930671411701"]},
    {"label": "酷诺", "url": "https://shop45996540o0794.1688.com", "pinned": ["979632972917"]},
]


def main() -> int:
    for seed in SEEDS:
        target = {
            "target_url": seed["url"],
            "crawl_strategy": "1688_shop_topn",
            "config_json": json.dumps({"top_n": 20, "pinned_offer_ids": seed["pinned"]}, ensure_ascii=False),
        }
        payload = crawl_shop(tenant_id=5, target=target, max_products=20)
        print(seed["label"], "products:", len(payload["products"]), "member:", payload["meta"]["member_id"], flush=True)
        for p in payload["products"][:5]:
            print(
                "  ",
                p.get("rank"),
                p.get("offer_id"),
                str(p.get("title"))[:28],
                p.get("price"),
                p.get("sale_text"),
                p.get("total_sales"),
                p.get("rebuy_rate"),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 跑冒烟（真实会话，租户 5 已登录）**

Run: `python scripts/_smoke_1688_monitor.py`
Expected: 三店各输出 ≥10 条商品，东博瑞 KRANK（930671411701）出现在结果中且 `total_sales` ≥ 100000；无 `MONITOR_AUTH_REQUIRED` / `MONITOR_PARSE_FAILED`。

- [ ] **Step 4: 提交**

```bash
git add backend/python/app/platforms/alibaba1688_shop_collector.py scripts/_smoke_1688_monitor.py
git commit -m "feat(1688-monitor): browser collector for shop bestsellers and pinned offers"
```

### Task 4: 1688 监控适配器 + 注册

**Files:**
- Create: `backend/python/app/platforms/alibaba1688_monitor_adapter.py`
- Modify: `backend/python/monitor_worker.py`（adapters 字典）
- Test: `backend/python/tests/test_alibaba1688_monitor_adapter.py`

**Interfaces:**
- Consumes: Task 3 的 `crawl_shop`
- Produces: `Alibaba1688MonitorAdapter(MonitorPlatformAdapter)`，`crawl_target(*, tenant_id, target, max_products) -> {"platform": "1688", "snapshot_at": str, "products": [...]}`（product 字段对齐 monitor 通用 schema + 1688 扩展字段，`daily_sales=0` 由 Task 5 的 worker 用累计差值回填）

- [ ] **Step 1: 写失败测试**

```python
import unittest
from unittest.mock import patch

from app.platforms.alibaba1688_monitor_adapter import Alibaba1688MonitorAdapter


class Alibaba1688MonitorAdapterTest(unittest.TestCase):
    def test_crawl_target_maps_products(self):
        fake_payload = {
            "platform": "1688",
            "snapshot_at": "2026-08-20 10:00:00",
            "products": [
                {
                    "offer_id": "930671411701",
                    "title": "东博瑞 KRANK HOOK",
                    "price": "0.5",
                    "sale_text": "已售10万+件",
                    "total_sales": 100000,
                    "rank": 1,
                    "listed_at": "2024-08-15",
                    "url": "https://detail.1688.com/offer/930671411701.html",
                    "shop_name": "深圳市东博瑞户外用品有限公司",
                    "shop_url": "https://shop16yx1905b2433.1688.com",
                    "shop_fans": 722,
                    "quality_rate": "100%",
                    "shop_return_rate": "73%",
                    "dropship_7d": "100以内",
                    "dropship_30d": "100以内",
                    "dropship_heat": 195,
                    "rebuy_rate": "复购率48.1%",
                    "attrs_json": "[{\"property\":\"品牌\",\"value\":\"东博瑞\"}]",
                    "is_pinned": 1,
                    "raw_json": "{}",
                }
            ],
            "shop": {},
            "meta": {"member_id": "b2b-x"},
        }
        with patch(
            "app.platforms.alibaba1688_monitor_adapter.crawl_shop",
            return_value=fake_payload,
        ):
            result = Alibaba1688MonitorAdapter().crawl_target(
                tenant_id=5,
                target={"target_url": "https://shop16yx1905b2433.1688.com"},
                max_products=20,
            )
        self.assertEqual(result["platform"], "1688")
        self.assertEqual(result["snapshot_at"], "2026-08-20 10:00:00")
        product = result["products"][0]
        self.assertEqual(product["product_id"], "930671411701")
        self.assertEqual(product["price"], 0.5)
        self.assertEqual(product["total_sales"], 100000)
        self.assertEqual(product["daily_sales"], 0)
        self.assertEqual(product["is_pinned"], 1)
        self.assertEqual(product["shop_name"], "深圳市东博瑞户外用品有限公司")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_alibaba1688_monitor_adapter.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 最小实现**

```python
"""1688 monitor platform adapter."""
from __future__ import annotations

from typing import Any

from app.platforms.alibaba1688_shop_collector import crawl_shop
from app.platforms.base import MonitorPlatformAdapter


class Alibaba1688MonitorAdapter(MonitorPlatformAdapter):
    def crawl_target(self, *, tenant_id: int, target: dict, max_products: int) -> dict[str, Any]:
        payload = crawl_shop(tenant_id=tenant_id, target=target, max_products=max_products)
        products = []
        for row in payload["products"]:
            try:
                price = float(str(row.get("price") or "").replace("¥", ""))
            except ValueError:
                price = 0.0
            products.append(
                {
                    "product_id": str(row["offer_id"]),
                    "product_name": str(row.get("title") or ""),
                    "category": str(row.get("category") or ""),
                    "price": price,
                    "daily_sales": 0,
                    "total_sales": int(row.get("total_sales") or 0),
                    "listed_at": str(row.get("listed_at") or "")[:10],
                    "url": str(row.get("url") or ""),
                    "shop_name": str(row.get("shop_name") or ""),
                    "shop_url": str(row.get("shop_url") or ""),
                    "rank": int(row.get("rank") or 0),
                    "price_range": str(row.get("price_range") or ""),
                    "sale_text": str(row.get("sale_text") or ""),
                    "dropship_7d": str(row.get("dropship_7d") or ""),
                    "dropship_30d": str(row.get("dropship_30d") or ""),
                    "dropship_heat": int(row.get("dropship_heat") or 0),
                    "rebuy_rate": str(row.get("rebuy_rate") or ""),
                    "shop_return_rate": str(row.get("shop_return_rate") or ""),
                    "quality_rate": str(row.get("quality_rate") or ""),
                    "shop_fans": int(row.get("shop_fans") or 0),
                    "attrs_json": str(row.get("attrs_json") or ""),
                    "is_pinned": int(row.get("is_pinned") or 0),
                    "status": str(row.get("status") or ""),
                    "expired": 1 if row.get("expired") else 0,
                    "raw_json": str(row.get("raw_json") or ""),
                }
            )
        return {
            "platform": "1688",
            "snapshot_at": payload["snapshot_at"],
            "products": products,
        }
```

- [ ] **Step 4: 注册适配器**

修改 `backend/python/monitor_worker.py`：

```python
from app.platforms.alibaba1688_monitor_adapter import Alibaba1688MonitorAdapter
from app.platforms.temu_monitor_adapter import TemuMonitorAdapter
```

并替换 `process_one_job` 内的 adapters 字典：

```python
        return process_next_pending_job(
            conn,
            adapters={"temu": TemuMonitorAdapter(), "1688": Alibaba1688MonitorAdapter()},
            report_root=report_root,
            worker_id=worker_id,
        )
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_alibaba1688_monitor_adapter.py -q`
Expected: PASS（1 passed）

- [ ] **Step 6: 提交**

```bash
git add backend/python/app/platforms/alibaba1688_monitor_adapter.py backend/python/monitor_worker.py backend/python/tests/test_alibaba1688_monitor_adapter.py
git commit -m "feat(1688-monitor): register 1688 monitor adapter"
```

### Task 5: Worker 日增量计算 + 新信号检测 + 落库扩展

**Files:**
- Modify: `backend/python/app/monitor_db.py`（MONITOR_RESULT_SCHEMA 增列）
- Modify: `backend/python/app/monitor_worker_service.py`（`analyze_products`、`persist_snapshot`）
- Test: `backend/python/tests/test_alibaba1688_monitor_analysis.py`

**Interfaces:**
- Consumes: 通用 worker 现有流程；Task 4 的 product 字段（`total_sales`、`status`、`expired`、`rank`）
- Produces: `analyze_products` 返回增加 `signals` 列表（`(signal_type, score, value, product_id)`）；`monitor_product_snapshot` 支持新列；`daily_sales` 由累计差值回填

- [ ] **Step 1: 更新 schema（新库建表）**

`backend/python/app/monitor_db.py` 中 `MONITOR_RESULT_SCHEMA` 的 `monitor_product_snapshot` 建表语句追加：

```sql
  shop_name TEXT NOT NULL DEFAULT '',
  shop_url TEXT NOT NULL DEFAULT '',
  rank INTEGER NOT NULL DEFAULT 0,
  price_range TEXT NOT NULL DEFAULT '',
  sale_text TEXT NOT NULL DEFAULT '',
  dropship_7d TEXT NOT NULL DEFAULT '',
  dropship_30d TEXT NOT NULL DEFAULT '',
  dropship_heat INTEGER NOT NULL DEFAULT 0,
  rebuy_rate TEXT NOT NULL DEFAULT '',
  shop_return_rate TEXT NOT NULL DEFAULT '',
  quality_rate TEXT NOT NULL DEFAULT '',
  shop_fans INTEGER NOT NULL DEFAULT 0,
  attrs_json TEXT NOT NULL DEFAULT '',
  is_pinned INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT '',
  expired INTEGER NOT NULL DEFAULT 0,
  suspicious INTEGER NOT NULL DEFAULT 0,
  raw_json TEXT NOT NULL DEFAULT '',
```

（插入在 `url TEXT NOT NULL DEFAULT '',` 与 `created_at` 之间。）

- [ ] **Step 2: 写失败测试**

```python
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.monitor_db import init_monitor_schema, init_monitor_result_schema
from app.monitor_worker_service import analyze_products, persist_snapshot


def _seed_snapshot(conn):
    conn.execute(
        """INSERT INTO monitor_snapshot (id, tenant_id, target_id, platform, snapshot_at, product_count,
           recent_launch_count, sales_outlier_count, report_md_path, report_xlsx_path, created_at)
           VALUES ('ms_prev', 1, 'mt_1', '1688', '2026-08-20 08:00:00', 1, 0, 0, '', '', '2026-08-20 08:00:00')"""
    )
    conn.execute(
        """INSERT INTO monitor_product_snapshot (
           id, tenant_id, snapshot_id, target_id, product_id, product_name, category, price,
           daily_sales, total_sales, listed_at, url, shop_name, shop_url, rank, price_range,
           sale_text, dropship_7d, dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
           quality_rate, shop_fans, attrs_json, is_pinned, status, expired, suspicious, raw_json, created_at)
           VALUES ('mps_prev', 1, 'ms_prev', 'mt_1', '930671411701', 'KRANK', '', 0.5,
           0, 50000, '2024-08-15', 'https://detail.1688.com/offer/930671411701.html',
           '东博瑞', '', 1, '', '已售5万+件', '', '', 0, '', '', '', 0, '', 1, 'published', 0, 0, '{}', '2026-08-20 08:00:00')"""
    )
    conn.commit()


class Alibaba1688MonitorAnalysisTest(unittest.TestCase):
    def test_daily_sales_delta_and_price_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            init_monitor_schema(conn)
            init_monitor_result_schema(conn)
            _seed_snapshot(conn)

            products = [
                {
                    "product_id": "930671411701",
                    "product_name": "KRANK",
                    "price": 0.6,
                    "total_sales": 51200,
                    "daily_sales": 0,
                    "listed_at": "2024-08-15",
                    "url": "https://detail.1688.com/offer/930671411701.html",
                    "rank": 1,
                    "status": "published",
                    "expired": 0,
                }
            ]
            analysis = analyze_products(conn, 1, "mt_1", "2026-08-20 10:00:00", products)
            self.assertEqual(products[0]["daily_sales"], 1200)  # 51200 - 50000
            self.assertNotIn("suspicious", products[0])
            types = {s[0] for s in analysis["signals"]}
            self.assertIn("price_change", types)

            persist_snapshot(
                conn,
                snapshot_id="ms_cur",
                tenant_id=1,
                target_id="mt_1",
                platform="1688",
                snapshot_at="2026-08-20 10:00:00",
                products=products,
                analysis=analysis,
                report_paths={"report_md_rel": "m.md", "report_xlsx_rel": "m.xlsx"},
            )
            row = conn.execute(
                "SELECT daily_sales, total_sales, shop_name, rank, status, suspicious FROM monitor_product_snapshot WHERE snapshot_id='ms_cur'"
            ).fetchone()
            self.assertEqual(row["daily_sales"], 1200)
            self.assertEqual(row["status"], "published")

    def test_suspicious_negative_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            init_monitor_schema(conn)
            init_monitor_result_schema(conn)
            _seed_snapshot(conn)
            products = [
                {
                    "product_id": "930671411701",
                    "product_name": "KRANK",
                    "price": 0.5,
                    "total_sales": 100,
                    "daily_sales": 0,
                    "listed_at": "2024-08-15",
                    "url": "",
                    "rank": 1,
                    "status": "published",
                    "expired": 0,
                }
            ]
            analyze_products(conn, 1, "mt_1", "2026-08-20 10:00:00", products)
            self.assertEqual(products[0]["suspicious"], 1)
            self.assertEqual(products[0]["daily_sales"], 0)
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_alibaba1688_monitor_analysis.py -q`
Expected: FAIL（daily_sales 未回填 / 列不存在）

- [ ] **Step 4: 实现 analyze_products 扩展**

替换 `backend/python/app/monitor_worker_service.py` 中 `analyze_products` 函数体：

```python
SUSPICIOUS_DELTA_CAP = 200000


def analyze_products(
    conn: sqlite3.Connection,
    tenant_id: int,
    target_id: str,
    snapshot_at: str,
    products: list[dict],
) -> dict:
    snapshot_day = snapshot_at[:10]
    prior_products = {
        row["product_id"]
        for row in conn.execute(
            """
            SELECT DISTINCT product_id
            FROM monitor_product_snapshot
            WHERE tenant_id = ? AND target_id = ?
            """,
            (tenant_id, target_id),
        ).fetchall()
    }
    history = {}
    for row in conn.execute(
        """
        SELECT product_id, AVG(daily_sales) AS avg_daily_sales
        FROM monitor_product_snapshot
        WHERE tenant_id = ? AND target_id = ?
        GROUP BY product_id
        """,
        (tenant_id, target_id),
    ).fetchall():
        history[row["product_id"]] = float(row["avg_daily_sales"] or 0)

    prior_totals: dict[str, dict] = {}
    for row in conn.execute(
        """
        SELECT p.product_id, p.total_sales, p.price, p.status, p.expired, s.snapshot_at
        FROM monitor_product_snapshot p
        JOIN monitor_snapshot s ON s.id = p.snapshot_id
        WHERE p.tenant_id = ? AND p.target_id = ?
        ORDER BY s.snapshot_at DESC
        """,
        (tenant_id, target_id),
    ).fetchall():
        pid = row["product_id"]
        if pid not in prior_totals:
            prior_totals[pid] = {
                "total_sales": int(row["total_sales"] or 0),
                "price": float(row["price"] or 0),
                "status": str(row["status"] or ""),
                "expired": int(row["expired"] or 0),
                "snapshot_at": row["snapshot_at"],
            }

    recent_launches = []
    sales_outliers = []
    signals = []
    for product in products:
        listed_at = str(product.get("listed_at") or "")
        product_id = str(product.get("product_id") or "")
        total_sales = int(product.get("total_sales") or 0)
        daily_sales = int(product.get("daily_sales") or 0)
        price = float(product.get("price") or 0)
        prior = prior_totals.get(product_id)
        if prior is None:
            if product.get("rank"):
                signals.append(("bestseller_new_entry", 1.0, json.dumps({"rank": product.get("rank")}), product_id))
        else:
            if daily_sales == 0:
                delta = total_sales - prior["total_sales"]
                if 0 <= delta <= SUSPICIOUS_DELTA_CAP:
                    daily_sales = delta
                else:
                    product["suspicious"] = 1
            old_price = prior["price"]
            if old_price and price and abs(old_price - price) > 0.001:
                signals.append(("price_change", 1.0, json.dumps({"old": old_price, "new": price}), product_id))
            if prior["expired"] and not int(product.get("expired") or 0):
                signals.append(("delist_or_relist", 1.0, json.dumps({"status": "relisted"}), product_id))
        product["daily_sales"] = daily_sales
        if is_recent_launch(snapshot_day, listed_at) and product_id not in prior_products:
            recent_launches.append(product)
        avg_daily = history.get(product_id, 0.0)
        if daily_sales >= 20 and (avg_daily <= 0 or daily_sales >= max(20, avg_daily * 1.5)):
            sales_outliers.append(product)

    current_ids = {str(p.get("product_id") or "") for p in products}
    for pid, prior in prior_totals.items():
        if pid not in current_ids and prior["status"] != "":
            signals.append(("delist_or_relist", 1.0, json.dumps({"status": "delisted"}), pid))

    return {
        "recent_launches": recent_launches,
        "sales_outliers": sales_outliers,
        "signals": signals,
    }
```

并在文件顶部确认 `import json` 已存在（若缺失则补 `import json`）。

- [ ] **Step 5: 扩展 persist_snapshot**

将 `persist_snapshot` 的 `monitor_product_snapshot` INSERT 替换为：

```python
    for product in products:
        conn.execute(
            """
            INSERT INTO monitor_product_snapshot (
              id, tenant_id, snapshot_id, target_id, product_id, product_name,
              category, price, daily_sales, total_sales, listed_at, url,
              shop_name, shop_url, rank, price_range, sale_text, dropship_7d,
              dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
              quality_rate, shop_fans, attrs_json, is_pinned, status, expired,
              suspicious, raw_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"mps_{snapshot_id}_{product['product_id']}",
                tenant_id,
                snapshot_id,
                target_id,
                product["product_id"],
                product["product_name"],
                product.get("category", ""),
                float(product.get("price") or 0),
                int(product.get("daily_sales") or 0),
                int(product.get("total_sales") or 0),
                product.get("listed_at", ""),
                product.get("url", ""),
                product.get("shop_name", ""),
                product.get("shop_url", ""),
                int(product.get("rank") or 0),
                product.get("price_range", ""),
                product.get("sale_text", ""),
                product.get("dropship_7d", ""),
                product.get("dropship_30d", ""),
                int(product.get("dropship_heat") or 0),
                product.get("rebuy_rate", ""),
                product.get("shop_return_rate", ""),
                product.get("quality_rate", ""),
                int(product.get("shop_fans") or 0),
                product.get("attrs_json", ""),
                int(product.get("is_pinned") or 0),
                product.get("status", ""),
                int(product.get("expired") or 0),
                int(product.get("suspicious") or 0),
                product.get("raw_json", ""),
                created_at,
            ),
        )
```

在 `persist_snapshot` 原有两个信号循环之后追加：

```python
    for signal_type, score, value, product_id in analysis.get("signals", []):
        conn.execute(
            """
            INSERT INTO monitor_signal (
              id, tenant_id, snapshot_id, target_id, product_id, signal_type, signal_score, signal_value, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"sig_{uuid.uuid4().hex}",
                tenant_id,
                snapshot_id,
                target_id,
                product_id,
                signal_type,
                float(score or 1.0),
                str(value or ""),
                created_at,
            ),
        )
```

`monitor_worker_service.py` 顶部需已导入 `json`（如缺失则添加）。

- [ ] **Step 6: 运行确认通过（新旧用例全绿）**

Run: `python -m pytest tests/test_alibaba1688_monitor_analysis.py tests/test_monitor_worker_service.py -q`
Expected: PASS（新增 2 + 既有用例全部通过）

- [ ] **Step 7: 提交**

```bash
git add backend/python/app/monitor_db.py backend/python/app/monitor_worker_service.py backend/python/tests/test_alibaba1688_monitor_analysis.py
git commit -m "feat(1688-monitor): daily-sales delta and extended signals in monitor worker"
```

### Task 6: 排程入队器 + 接入 worker

**Files:**
- Create: `backend/python/app/monitor_schedule_enqueuer.py`
- Modify: `backend/python/monitor_worker.py`
- Test: `backend/python/tests/test_monitor_schedule_enqueuer.py`

**Interfaces:**
- Consumes: `monitor_schedule` / `monitor_target` / `monitor_job` 表
- Produces: `enqueue_due_jobs(conn, *, now=None, jitter_seconds=600) -> list[str]`

- [ ] **Step 1: 写失败测试**

```python
import sqlite3
import unittest

from app.monitor_db import init_monitor_schema
from app.monitor_schedule_enqueuer import enqueue_due_jobs


def _seed(conn):
    conn.execute(
        """INSERT INTO monitor_target (id, tenant_id, platform, target_type, label, target_url, host,
           status, crawl_strategy, freshness_minutes, latest_snapshot_id, latest_snapshot_at, created_at, updated_at)
           VALUES ('mt_1', 1, '1688', 'shop', '东博瑞', 'https://shop16yx1905b2433.1688.com',
           'shop16yx1905b2433.1688.com', 'active', '1688_shop_topn', 120, NULL, NULL, '2026-08-20 00:00:00', '2026-08-20 00:00:00')"""
    )
    conn.execute(
        """INSERT INTO monitor_schedule (id, tenant_id, target_id, enabled, schedule_type, cron_expr,
           interval_minutes, next_run_at, last_run_at, max_products, retry_limit, created_at, updated_at)
           VALUES ('msch_1', 1, 'mt_1', 1, 'interval', '', 120, '2026-08-20 09:00:00', NULL, 20, 1,
           '2026-08-20 00:00:00', '2026-08-20 00:00:00')"""
    )
    conn.commit()


class MonitorScheduleEnqueuerTest(unittest.TestCase):
    def test_enqueues_due_job_and_advances_next_run(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_monitor_schema(conn)
        _seed(conn)
        job_ids = enqueue_due_jobs(conn, now="2026-08-20 10:00:00", jitter_seconds=0)
        self.assertEqual(len(job_ids), 1)
        job = conn.execute("SELECT * FROM monitor_job WHERE id = ?", (job_ids[0],)).fetchone()
        self.assertEqual(job["trigger_type"], "scheduled")
        self.assertEqual(job["platform"], "1688")
        sched = conn.execute("SELECT * FROM monitor_schedule WHERE id = 'msch_1'").fetchone()
        self.assertEqual(sched["next_run_at"], "2026-08-20 12:00:00")

    def test_skips_target_with_running_job(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_monitor_schema(conn)
        _seed(conn)
        conn.execute(
            """INSERT INTO monitor_job (id, tenant_id, target_id, schedule_id, platform, trigger_type,
               force, status, attempt_no, queued_at, started_at, finished_at, worker_id, error_code,
               error_message, error_detail, snapshot_id, created_by, reason)
               VALUES ('mj_busy', 1, 'mt_1', 'msch_1', '1688', 'manual', 0, 'running', 1,
               '2026-08-20 09:00:00', '2026-08-20 09:00:01', NULL, '', NULL, NULL, NULL, NULL, NULL, '')"""
        )
        conn.commit()
        job_ids = enqueue_due_jobs(conn, now="2026-08-20 10:00:00", jitter_seconds=0)
        self.assertEqual(job_ids, [])
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_monitor_schedule_enqueuer.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 最小实现**

```python
"""Enqueue due monitor jobs from monitor_schedule."""
from __future__ import annotations

import random
import sqlite3
import uuid
from datetime import datetime, timedelta


def enqueue_due_jobs(
    conn: sqlite3.Connection,
    *,
    now: str | None = None,
    jitter_seconds: int = 600,
) -> list[str]:
    if now is None:
        from app.monitor_worker_service import now_text

        now = now_text()
    rows = conn.execute(
        """
        SELECT s.id AS schedule_id, s.tenant_id, s.target_id, s.interval_minutes, t.platform
        FROM monitor_schedule s
        JOIN monitor_target t ON t.id = s.target_id AND t.tenant_id = s.tenant_id
        WHERE s.enabled = 1 AND t.status = 'active'
          AND (s.next_run_at IS NULL OR s.next_run_at <= ?)
        """,
        (now,),
    ).fetchall()
    enqueued: list[str] = []
    for row in rows:
        target_id = row["target_id"]
        busy = conn.execute(
            """
            SELECT 1 FROM monitor_job
            WHERE tenant_id = ? AND target_id = ? AND status IN ('pending', 'running')
            LIMIT 1
            """,
            (row["tenant_id"], target_id),
        ).fetchone()
        if busy:
            continue
        job_id = f"mj_{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO monitor_job (
              id, tenant_id, target_id, schedule_id, platform, trigger_type, force, status,
              attempt_no, queued_at, started_at, finished_at, worker_id, error_code, error_message,
              error_detail, snapshot_id, created_by, reason
            ) VALUES (?, ?, ?, ?, ?, 'scheduled', 0, 'pending', 1, ?, NULL, NULL, '', NULL, NULL, NULL, NULL, NULL, 'scheduled')
            """,
            (job_id, row["tenant_id"], target_id, row["schedule_id"], row["platform"], now),
        )
        interval_minutes = max(1, int(row["interval_minutes"] or 1440))
        next_run = _next_run_at(now, interval_minutes, jitter_seconds)
        conn.execute(
            "UPDATE monitor_schedule SET next_run_at = ?, last_run_at = ?, updated_at = ? WHERE id = ?",
            (next_run, now, now, row["schedule_id"]),
        )
        enqueued.append(job_id)
    conn.commit()
    return enqueued


def _next_run_at(now: str, interval_minutes: int, jitter_seconds: int) -> str:
    base = datetime.strptime(now[:19], "%Y-%m-%d %H:%M:%S")
    jitter = random.randint(0, max(0, jitter_seconds))
    return (base + timedelta(minutes=interval_minutes, seconds=jitter)).strftime("%Y-%m-%d %H:%M:%S")
```

- [ ] **Step 4: 接入 monitor_worker.py**

在 `monitor_worker.py` 顶部 import：

```python
from app.monitor_schedule_enqueuer import enqueue_due_jobs
```

在 `process_one_job` 中 `init_monitor_result_schema(conn)` 之后插入：

```python
        enqueue_due_jobs(conn)
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_monitor_schedule_enqueuer.py -q`
Expected: PASS（2 passed）

- [ ] **Step 6: 提交**

```bash
git add backend/python/app/monitor_schedule_enqueuer.py backend/python/monitor_worker.py backend/python/tests/test_monitor_schedule_enqueuer.py
git commit -m "feat(1688-monitor): schedule enqueuer for monitor_schedule"
```

### Task 7: Java V45 表结构迁移

**Files:**
- Create: `backend/java/src/main/java/com/crosshub/config/migration/V45Alibaba1688MonitorMigration.java`

**Interfaces:**
- Consumes: `JdbcTemplate`；现有 `monitor_product_snapshot` / `monitor_target` 表
- Produces: 1688 列 + `config_json` + `suspicious` 列（幂等）

- [ ] **Step 1: 实现迁移**

```java
package com.crosshub.config.migration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
@Order(45)
public class V45Alibaba1688MonitorMigration {
    private static final Logger log = LoggerFactory.getLogger(V45Alibaba1688MonitorMigration.class);

    private final JdbcTemplate jdbc;

    public V45Alibaba1688MonitorMigration(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        addColumnIfMissing("monitor_product_snapshot", "shop_name", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "shop_url", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "rank", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "price_range", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "sale_text", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "dropship_7d", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "dropship_30d", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "dropship_heat", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "rebuy_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "shop_return_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "quality_rate", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "shop_fans", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "attrs_json", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "is_pinned", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "status", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_product_snapshot", "expired", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "suspicious", "INTEGER DEFAULT 0");
        addColumnIfMissing("monitor_product_snapshot", "raw_json", "TEXT DEFAULT ''");
        addColumnIfMissing("monitor_target", "config_json", "TEXT DEFAULT ''");
        log.info("V45 alibaba1688 monitor migration applied");
    }

    private void addColumnIfMissing(String table, String column, String ddl) {
        List<Map<String, Object>> columns = jdbc.queryForList("PRAGMA table_info(" + table + ")");
        boolean exists = columns.stream()
                .anyMatch(c -> column.equalsIgnoreCase(String.valueOf(c.get("name"))));
        if (!exists) {
            jdbc.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + ddl);
        }
    }
}
```

- [ ] **Step 2: 验证**

Run（backend/java）：`mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 3: 提交**

```bash
git add backend/java/src/main/java/com/crosshub/config/migration/V45Alibaba1688MonitorMigration.java
git commit -m "feat(1688-monitor): V45 migration for 1688 monitor columns"
```

### Task 8: Java 1688 URL 校验器 + 平台分发

**Files:**
- Create: `backend/java/src/main/java/com/crosshub/monitor/util/Alibaba1688MonitorUrlValidator.java`
- Create: `backend/java/src/test/java/com/crosshub/monitor/Alibaba1688MonitorUrlValidatorTest.java`
- Modify: `backend/java/src/main/java/com/crosshub/monitor/service/impl/MonitorServiceImpl.java`（`validateAndMaybeCanonicalizeTemuShopUrl`）

**Interfaces:**
- Consumes: 无（新校验器）；`MonitorServiceImpl`
- Produces: `Alibaba1688MonitorUrlValidator.requireValidForCreate(url, crawlStrategy)`、`canonicalize(url)`

- [ ] **Step 1: 写失败测试**

```java
package com.crosshub.monitor;

import com.crosshub.monitor.util.Alibaba1688MonitorUrlValidator;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class Alibaba1688MonitorUrlValidatorTest {

    @Test
    void canonicalize_acceptsShopAndOfferUrls() {
        assertEquals(
                "https://shop16yx1905b2433.1688.com",
                Alibaba1688MonitorUrlValidator.canonicalize("https://shop16yx1905b2433.1688.com")
        );
        assertEquals(
                "https://detail.1688.com/offer/930671411701.html",
                Alibaba1688MonitorUrlValidator.canonicalize("https://m.1688.com/offer/930671411701.html")
        );
    }

    @Test
    void requireValidForCreate_rejectsUnrelatedUrl() {
        assertThrows(Exception.class, () ->
                Alibaba1688MonitorUrlValidator.requireValidForCreate(
                        "https://www.temu.com/mall.html?mall_id=1",
                        "1688_shop_topn"
                )
        );
    }
}
```

- [ ] **Step 2: 运行确认失败**

Run（backend/java）：`mvn -q -Dtest=Alibaba1688MonitorUrlValidatorTest test`
Expected: FAIL（编译错误：找不到类）

- [ ] **Step 3: 最小实现**

```java
package com.crosshub.monitor.util;

import com.crosshub.common.AppErrorCode;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class Alibaba1688MonitorUrlValidator {
    private static final Pattern SHOP_HOST = Pattern.compile("(?i)^shop\\d+\\.1688\\.com$");
    private static final Pattern OFFER_PATH = Pattern.compile("(?i)/offer/(\\d+)\\.html");

    private Alibaba1688MonitorUrlValidator() {
    }

    public static void requireValidForCreate(String url, String crawlStrategy) {
        String canonical = canonicalize(url);
        boolean strategyExpectsOffer = "1688_pinned_offers".equalsIgnoreCase(crawlStrategy);
        boolean isOffer = OFFER_PATH.matcher(pathOf(url)).find();
        if (strategyExpectsOffer != isOffer) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    AppErrorCode.MONITOR_TARGET_URL_INVALID.getUserMessage()
            );
        }
        if (canonical == null || canonical.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    AppErrorCode.MONITOR_TARGET_URL_INVALID.getUserMessage()
            );
        }
    }

    public static String canonicalize(String url) {
        if (url == null || url.isBlank()) {
            return "";
        }
        URI uri;
        try {
            uri = URI.create(url.trim());
        } catch (Exception ex) {
            return "";
        }
        String host = uri.getHost();
        if (host == null) {
            return "";
        }
        String hostLower = host.toLowerCase(Locale.ROOT);
        if (SHOP_HOST.matcher(hostLower).matches()) {
            return "https://" + hostLower;
        }
        Matcher m = OFFER_PATH.matcher(pathOf(url));
        if (m.find()) {
            return "https://detail.1688.com/offer/" + m.group(1) + ".html";
        }
        return "";
    }

    private static String pathOf(String url) {
        try {
            return URI.create(url.trim()).getPath() == null ? "" : URI.create(url.trim()).getPath();
        } catch (Exception ex) {
            return "";
        }
    }
}
```

- [ ] **Step 4: 接入 MonitorServiceImpl 平台分发**

修改 `validateAndMaybeCanonicalizeTemuShopUrl`：

```java
    private String validateAndMaybeCanonicalizeTemuShopUrl(
            String platform,
            String targetType,
            String crawlStrategy,
            String targetUrl
    ) {
        if ("1688".equalsIgnoreCase(platform) && "shop".equalsIgnoreCase(targetType)) {
            Alibaba1688MonitorUrlValidator.requireValidForCreate(targetUrl, crawlStrategy);
            return Alibaba1688MonitorUrlValidator.canonicalize(targetUrl);
        }
        boolean temuShopListing = "temu".equalsIgnoreCase(platform)
                && "shop".equalsIgnoreCase(targetType)
                && "store_listing".equalsIgnoreCase(crawlStrategy);
        if (!temuShopListing) {
            return targetUrl;
        }
        TemuMonitorUrlValidator.requireValidForCreate(targetUrl);
        return TemuMonitorUrlValidator.canonicalize(targetUrl);
    }
```

文件顶部补 import：`import com.crosshub.monitor.util.Alibaba1688MonitorUrlValidator;`

- [ ] **Step 5: 运行确认通过**

Run（backend/java）：`mvn -q -Dtest=Alibaba1688MonitorUrlValidatorTest test`
Expected: PASS（2 tests）

- [ ] **Step 6: 提交**

```bash
git add backend/java/src/main/java/com/crosshub/monitor/util/Alibaba1688MonitorUrlValidator.java backend/java/src/test/java/com/crosshub/monitor/Alibaba1688MonitorUrlValidatorTest.java backend/java/src/main/java/com/crosshub/monitor/service/impl/MonitorServiceImpl.java
git commit -m "feat(1688-monitor): 1688 monitor url validator and platform dispatch"
```

### Task 9: Java trend / signals / latest-products 接口

**Files:**
- Modify: `backend/java/src/main/java/com/crosshub/monitor/service/MonitorService.java`
- Modify: `backend/java/src/main/java/com/crosshub/monitor/service/impl/MonitorServiceImpl.java`
- Modify: `backend/java/src/main/java/com/crosshub/monitor/controller/MonitorController.java`

**Interfaces:**
- Consumes: Task 7 的新列
- Produces: `List<Map<String,Object>> getTrend(String targetId, int days, String productId)`、`List<Map<String,Object>> getSignals(String targetId, int limit)`；`getLatest` 响应增加 `products`

- [ ] **Step 1: 扩展 MonitorService 接口**

在 `MonitorService.java` 接口中追加：

```java
    List<Map<String, Object>> getTrend(String targetId, int days, String productId);

    List<Map<String, Object>> getSignals(String targetId, int limit);
```

- [ ] **Step 2: 实现（MonitorServiceImpl）**

在类中追加：

```java
    @Override
    public List<Map<String, Object>> getTrend(String targetId, int days, String productId) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(targetId, tenantId);
        int safeDays = Math.max(1, Math.min(days, 90));
        String since = LocalDateTime.now().minusDays(safeDays).format(TS);
        StringBuilder sql = new StringBuilder("""
                SELECT p.product_id, p.product_name, s.snapshot_at, p.price, p.total_sales,
                       p.daily_sales, p.rank, p.sale_text, p.is_pinned
                FROM monitor_product_snapshot p
                JOIN monitor_snapshot s ON s.id = p.snapshot_id
                WHERE p.tenant_id = ? AND p.target_id = ? AND s.snapshot_at >= ?
                """);
        List<Object> args = new ArrayList<>(List.of(tenantId, targetId, since));
        if (productId != null && !productId.isBlank()) {
            sql.append(" AND p.product_id = ?");
            args.add(productId.trim());
        }
        sql.append(" ORDER BY s.snapshot_at ASC, p.rank ASC");
        return jdbc.query(sql.toString(), (rs, rn) -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("product_id", rs.getString("product_id"));
            row.put("product_name", rs.getString("product_name"));
            row.put("snapshot_at", rs.getString("snapshot_at"));
            row.put("price", rs.getDouble("price"));
            row.put("total_sales", rs.getInt("total_sales"));
            row.put("daily_sales", rs.getInt("daily_sales"));
            row.put("rank", rs.getInt("rank"));
            row.put("sale_text", rs.getString("sale_text"));
            row.put("is_pinned", rs.getInt("is_pinned"));
            return row;
        }, args.toArray());
    }

    @Override
    public List<Map<String, Object>> getSignals(String targetId, int limit) {
        Long tenantId = dataScopeService.requireTenantId();
        requireTargetRow(targetId, tenantId);
        int safeLimit = Math.max(1, Math.min(limit, 200));
        return jdbc.query("""
                SELECT s.signal_type, s.signal_score, s.signal_value, s.created_at,
                       p.product_id, p.product_name, p.price, p.total_sales, p.daily_sales, p.url
                FROM monitor_signal s
                LEFT JOIN monitor_product_snapshot p
                  ON p.tenant_id = s.tenant_id AND p.snapshot_id = s.snapshot_id AND p.product_id = s.product_id
                WHERE s.tenant_id = ? AND s.target_id = ?
                ORDER BY s.created_at DESC
                LIMIT ?
                """, (rs, rn) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("signal_type", rs.getString("signal_type"));
                    row.put("signal_score", rs.getDouble("signal_score"));
                    row.put("signal_value", rs.getString("signal_value"));
                    row.put("created_at", rs.getString("created_at"));
                    row.put("product_id", rs.getString("product_id"));
                    row.put("product_name", rs.getString("product_name"));
                    row.put("price", rs.getDouble("price"));
                    row.put("total_sales", rs.getInt("total_sales"));
                    row.put("daily_sales", rs.getInt("daily_sales"));
                    row.put("url", rs.getString("url"));
                    return row;
                }, tenantId, targetId, safeLimit);
    }
```

并在 `getLatest` 中，`out.put("reason", ...)` 之后追加（`out` 为 `Map<String, Object>`，`products` 变量在 `latestSnapshotId` 非空分支内填充）：

```java
        List<Map<String, Object>> products = List.of();
        if (!latestSnapshotId.isBlank()) {
            products = jdbc.query("""
                    SELECT product_id, product_name, category, price, daily_sales, total_sales,
                           listed_at, url, shop_name, shop_url, rank, price_range, sale_text,
                           dropship_7d, dropship_30d, dropship_heat, rebuy_rate, shop_return_rate,
                           quality_rate, shop_fans, is_pinned, suspicious
                    FROM monitor_product_snapshot
                    WHERE tenant_id = ? AND snapshot_id = ?
                    ORDER BY rank ASC, product_id ASC
                    LIMIT 200
                    """, (rs, rn) -> {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("product_id", rs.getString("product_id"));
                        row.put("product_name", rs.getString("product_name"));
                        row.put("category", rs.getString("category"));
                        row.put("price", rs.getDouble("price"));
                        row.put("daily_sales", rs.getInt("daily_sales"));
                        row.put("total_sales", rs.getInt("total_sales"));
                        row.put("listed_at", rs.getString("listed_at"));
                        row.put("url", rs.getString("url"));
                        row.put("shop_name", rs.getString("shop_name"));
                        row.put("shop_url", rs.getString("shop_url"));
                        row.put("rank", rs.getInt("rank"));
                        row.put("price_range", rs.getString("price_range"));
                        row.put("sale_text", rs.getString("sale_text"));
                        row.put("dropship_7d", rs.getString("dropship_7d"));
                        row.put("dropship_30d", rs.getString("dropship_30d"));
                        row.put("dropship_heat", rs.getInt("dropship_heat"));
                        row.put("rebuy_rate", rs.getString("rebuy_rate"));
                        row.put("shop_return_rate", rs.getString("shop_return_rate"));
                        row.put("quality_rate", rs.getString("quality_rate"));
                        row.put("shop_fans", rs.getInt("shop_fans"));
                        row.put("is_pinned", rs.getInt("is_pinned"));
                        row.put("suspicious", rs.getInt("suspicious"));
                        return row;
                    }, tenantId, latestSnapshotId);
        }
        out.put("products", products);
```

- [ ] **Step 3: 新增 Controller 路由**

```java
    @GetMapping("/targets/{id}/trend")
    public Map<String, Object> trend(
            @PathVariable String id,
            @RequestParam(defaultValue = "30") int days,
            @RequestParam(required = false) String product_id
    ) {
        return ApiResult.ok(monitorService.getTrend(id, days, product_id));
    }

    @GetMapping("/targets/{id}/signals")
    public Map<String, Object> signals(
            @PathVariable String id,
            @RequestParam(defaultValue = "50") int limit
    ) {
        return ApiResult.ok(monitorService.getSignals(id, limit));
    }
```

- [ ] **Step 4: 编译验证**

Run（backend/java）：`mvn -q compile`
Expected: BUILD SUCCESS

- [ ] **Step 5: 提交**

```bash
git add backend/java/src/main/java/com/crosshub/monitor/service/MonitorService.java backend/java/src/main/java/com/crosshub/monitor/service/impl/MonitorServiceImpl.java backend/java/src/main/java/com/crosshub/monitor/controller/MonitorController.java
git commit -m "feat(1688-monitor): trend, signals and latest-products APIs"
```

### Task 10: 前端 API 层

**Files:**
- Create: `dev/vue-site/src/api/alibaba1688MonitorApi.js`

**Interfaces:**
- Consumes: `service`（`./request` 的 axios 实例）
- Produces: `list1688MonitorTargets / create1688MonitorTarget / update1688MonitorTarget / delete1688MonitorTarget / update1688MonitorSchedule / trigger1688MonitorTarget / fetch1688MonitorLatest / fetch1688MonitorTrend / fetch1688MonitorSignals`

- [ ] **Step 1: 实现**

```js
import { service } from './request'

export async function list1688MonitorTargets() {
  const res = await service.get('/api/monitor/targets', { params: { platform: '1688' } })
  return res?.data ?? res
}

export async function create1688MonitorTarget(payload) {
  const res = await service.post('/api/monitor/targets', payload)
  return res?.data ?? res
}

export async function update1688MonitorTarget(id, payload) {
  const res = await service.put(`/api/monitor/targets/${id}`, payload)
  return res?.data ?? res
}

export async function delete1688MonitorTarget(id) {
  const res = await service.delete(`/api/monitor/targets/${id}`)
  return res?.data ?? res
}

export async function update1688MonitorSchedule(targetId, payload) {
  const res = await service.put(`/api/monitor/targets/${targetId}/schedule`, payload)
  return res?.data ?? res
}

export async function trigger1688MonitorTarget(targetId, payload = {}) {
  const res = await service.post(`/api/monitor/targets/${targetId}/trigger`, payload)
  return res?.data ?? res
}

export async function fetch1688MonitorLatest(targetId) {
  const res = await service.get(`/api/monitor/targets/${targetId}/latest`)
  return res?.data ?? res
}

export async function fetch1688MonitorTrend(targetId, { days = 30, productId = '' } = {}) {
  const params = { days }
  if (productId) params.product_id = productId
  const res = await service.get(`/api/monitor/targets/${targetId}/trend`, { params })
  return res?.data ?? res
}

export async function fetch1688MonitorSignals(targetId, limit = 50) {
  const res = await service.get(`/api/monitor/targets/${targetId}/signals`, { params: { limit } })
  return res?.data ?? res
}
```

- [ ] **Step 2: 验证**

Run（dev/vue-site）：`npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**

```bash
git add dev/vue-site/src/api/alibaba1688MonitorApi.js
git commit -m "feat(1688-monitor): frontend monitor api layer"
```

### Task 11: 前端竞店监控面板 + 模块 Tab

**Files:**
- Create: `dev/vue-site/src/components/alibaba1688/Alibaba1688MonitorPanel.vue`
- Modify: `dev/vue-site/src/views/alibaba1688/Alibaba1688ModuleView.vue`

**Interfaces:**
- Consumes: Task 10 API；`backendReady` / `stores` props（沿用其他 Panel 的约定）
- Produces: `Alibaba1688MonitorPanel.vue`（props: `backendReady`；emits: 无）

- [ ] **Step 1: 实现面板组件**

```vue
<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  create1688MonitorTarget,
  delete1688MonitorTarget,
  fetch1688MonitorLatest,
  fetch1688MonitorSignals,
  fetch1688MonitorTrend,
  list1688MonitorTargets,
  trigger1688MonitorTarget,
  update1688MonitorSchedule,
} from '@/api/alibaba1688MonitorApi'

const props = defineProps({
  backendReady: { type: Boolean, default: false },
})

const targets = ref([])
const selectedTargetId = ref('')
const latest = ref(null)
const products = ref([])
const signals = ref([])
const trend = ref([])
const trendProductId = ref('')
const loading = ref(false)
const showAdd = ref(false)
const form = ref({
  label: '',
  target_url: '',
  crawl_strategy: '1688_shop_topn',
  top_n: 20,
  pinned_offer_ids: '',
  interval_minutes: 120,
  webhook_url: '',
})

async function loadTargets() {
  if (!props.backendReady) return
  try {
    const data = await list1688MonitorTargets()
    targets.value = Array.isArray(data) ? data : []
    if (!selectedTargetId.value && targets.value.length) selectedTargetId.value = targets.value[0].id
    if (selectedTargetId.value) await loadLatest()
  } catch (error) {
    ElMessage.error(error?.message || '加载 1688 竞店监控失败')
  }
}

async function loadLatest() {
  if (!selectedTargetId.value) return
  loading.value = true
  try {
    const data = await fetch1688MonitorLatest(selectedTargetId.value)
    latest.value = data
    products.value = Array.isArray(data?.products) ? data.products : []
    signals.value = await fetch1688MonitorSignals(selectedTargetId.value, 50)
    await loadTrend()
  } catch (error) {
    ElMessage.error(error?.message || '加载快照失败')
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  trend.value = await fetch1688MonitorTrend(selectedTargetId.value, {
    days: 30,
    productId: trendProductId.value,
  })
  renderTrend()
}

function renderTrend() {
  const chartEl = document.getElementById('a1688-monitor-trend')
  if (!chartEl) return
  const chart = echarts.init(chartEl)
  const seriesMap = {}
  for (const row of trend.value) {
    if (!seriesMap[row.product_id]) seriesMap[row.product_id] = []
    seriesMap[row.product_id].push([row.snapshot_at, row.total_sales])
  }
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll' },
    xAxis: { type: 'category' },
    yAxis: { type: 'value' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: Object.entries(seriesMap).map(([pid, points]) => ({
      name: pid,
      type: 'line',
      data: points,
      showSymbol: false,
    })),
  })
}

async function trigger(targetId) {
  try {
    await trigger1688MonitorTarget(targetId, { force: true, bypass_cooldown: true, reason: 'manual refresh' })
    ElMessage.success('已触发刷新，请稍后查看最新快照')
  } catch (error) {
    ElMessage.error(error?.message || '触发失败')
  }
}

async function saveTarget() {
  const payload = {
    label: form.value.label,
    target_url: form.value.target_url,
    target_type: 'shop',
    platform: '1688',
    crawl_strategy: form.value.crawl_strategy,
    config_json: JSON.stringify({
      top_n: Number(form.value.top_n) || 20,
      pinned_offer_ids: form.value.pinned_offer_ids.split(',').map((s) => s.trim()).filter(Boolean),
      webhook_url: form.value.webhook_url.trim(),
    }),
  }
  try {
    const created = await create1688MonitorTarget(payload)
    if (created?.id) {
      await update1688MonitorSchedule(created.id, {
        enabled: true,
        schedule_type: 'interval',
        interval_minutes: Number(form.value.interval_minutes) || 120,
        max_products: Number(form.value.top_n) || 20,
        retry_limit: 1,
      })
    }
    showAdd.value = false
    form.value.pinned_offer_ids = ''
    await loadTargets()
    ElMessage.success('店铺监控已添加')
  } catch (error) {
    ElMessage.error(error?.message || '添加失败')
  }
}

async function removeTarget(targetId) {
  try {
    await ElMessageBox.confirm('确认删除该监控目标？历史快照会保留。', '删除确认')
    await delete1688MonitorTarget(targetId)
    if (selectedTargetId.value === targetId) selectedTargetId.value = ''
    await loadTargets()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error?.message || '删除失败')
  }
}

function thumbSrc(row) {
  const raw = String(row?.image_url || row?.imageUrl || '').trim()
  if (!raw) return ''
  if (raw.startsWith('//')) return 'https:' + raw
  return raw
}

onMounted(() => void loadTargets())
defineExpose({ loadTargets })
</script>

<template>
  <div class="a1688-monitor">
    <div class="toolbar">
      <el-button type="primary" :disabled="!backendReady" @click="showAdd = true">添加店铺监控</el-button>
      <el-button :disabled="!selectedTargetId" :loading="loading" @click="loadLatest">刷新快照</el-button>
    </div>

    <el-dialog v-model="showAdd" title="添加 1688 店铺监控" width="560px">
      <el-form label-width="110px">
        <el-form-item label="店铺名称"><el-input v-model="form.label" placeholder="如：东博瑞" /></el-form-item>
        <el-form-item label="店铺/商品链接">
          <el-input v-model="form.target_url" placeholder="https://shop16yx1905b2433.1688.com" />
        </el-form-item>
        <el-form-item label="监控类型">
          <el-select v-model="form.crawl_strategy">
            <el-option label="店铺爆款 Top N" value="1688_shop_topn" />
            <el-option label="指定商品盯梢" value="1688_pinned_offers" />
          </el-select>
        </el-form-item>
        <el-form-item label="Top N"><el-input-number v-model="form.top_n" :min="1" :max="50" /></el-form-item>
        <el-form-item label="盯梢商品">
          <el-input v-model="form.pinned_offer_ids" placeholder="offerId，逗号分隔，如 930671411701,867473865842" />
        </el-form-item>
        <el-form-item label="轮询间隔"><el-select v-model="form.interval_minutes">
          <el-option label="60 分钟" :value="60" />
          <el-option label="120 分钟" :value="120" />
        </el-select></el-form-item>
        <el-form-item label="Webhook"><el-input v-model="form.webhook_url" placeholder="钉钉/企微机器人地址（可选）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="saveTarget">保存</el-button>
      </template>
    </el-dialog>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>监控店铺</template>
          <el-table :data="targets" size="small" highlight-current-row @current-change="(row) => { selectedTargetId = row?.id || ''; loadLatest() }">
            <el-table-column prop="label" label="店铺" />
            <el-table-column label="状态" width="70">
              <template #default="{ row }">{{ row.status === 'active' ? '监控中' : '停用' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="130">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="trigger(row.id)">立即刷新</el-button>
                <el-button link type="danger" size="small" @click="removeTarget(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            爆款榜
            <span v-if="latest?.latest_snapshot_at" style="float: right; font-size: 12px; color: #999">
              最近快照：{{ latest.latest_snapshot_at }}
            </span>
          </template>
          <el-table :data="products" size="small" max-height="420">
            <el-table-column prop="rank" label="排名" width="55" />
            <el-table-column label="商品" min-width="220">
              <template #default="{ row }">
                <a :href="row.url" target="_blank" rel="noopener">
                  <el-image :src="thumbSrc(row)" fit="cover" style="width: 36px; height: 36px; vertical-align: middle" />
                  <span style="margin-left: 6px">{{ row.product_name }}</span>
                </a>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="70" />
            <el-table-column prop="total_sales" label="累计销量" width="90" />
            <el-table-column prop="daily_sales" label="日增量" width="80" />
            <el-table-column prop="dropship_7d" label="代发7天" width="90" />
            <el-table-column prop="rebuy_rate" label="复购率" width="90" />
            <el-table-column label="状态" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.expired" type="danger" size="small">下架</el-tag>
                <el-tag v-else type="success" size="small">在售</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        累计销量趋势（30 天）
        <el-select v-model="trendProductId" size="small" style="float: right; width: 220px" @change="loadTrend">
          <el-option label="全部商品" value="" />
          <el-option v-for="p in products" :key="p.product_id" :label="p.product_name" :value="p.product_id" />
        </el-select>
      </template>
      <div id="a1688-monitor-trend" style="height: 320px"></div>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>告警信号</template>
      <el-table :data="signals" size="small">
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="signal_type" label="类型" width="140" />
        <el-table-column prop="product_name" label="商品" min-width="180" />
        <el-table-column prop="signal_value" label="详情" min-width="220" />
      </el-table>
    </el-card>
  </div>
</template>
```

- [ ] **Step 2: 接入模块 Tab**

`Alibaba1688ModuleView.vue` 的 `<script setup>` 增加：

```js
import Alibaba1688MonitorPanel from '@/components/alibaba1688/Alibaba1688MonitorPanel.vue'
```

在 `<el-tab-pane name="peer-bestsellers" ...>` 之后增加：

```html
        <el-tab-pane name="monitor" label="竞店监控">
          <Alibaba1688MonitorPanel :backend-ready="backendReady" />
        </el-tab-pane>
```

- [ ] **Step 3: 构建验证**

Run（dev/vue-site）：`npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add dev/vue-site/src/components/alibaba1688/Alibaba1688MonitorPanel.vue dev/vue-site/src/views/alibaba1688/Alibaba1688ModuleView.vue
git commit -m "feat(1688-monitor): competitor monitor panel and module tab"
```

### Task 12: 集成冒烟与运行手册

**Files:**
- Modify: `README.md`（或 `docs/dev-handover.md`，追加运行说明）

- [ ] **Step 1: 全量 Python 单测**

Run（backend/python）：`python -m pytest tests/ -q`
Expected: 全部通过（含既有 Temu/monitor 用例）

- [ ] **Step 2: 端到端冒烟（真实三家店铺）**

Run（repo 根）：`python scripts/_smoke_1688_monitor.py`
Expected: 三店各 ≥10 条商品；东博瑞 KRANK `total_sales` ≥ 100000；无风控/登录错误

- [ ] **Step 3: Worker 全链路验证**

启动 monitor worker 并触发一次真实任务：

```bash
cd backend/python
python monitor_worker.py --once
```

随后通过 Java API 校验：

```bash
curl -s "http://127.0.0.1:8080/api/monitor/targets?platform=1688" | head -c 500
curl -s "http://127.0.0.1:8080/api/monitor/targets/{id}/latest" | head -c 800
curl -s "http://127.0.0.1:8080/api/monitor/targets/{id}/trend?days=30" | head -c 500
```

Expected: 目标存在、最新快照含商品列表、趋势返回时间序列。

- [ ] **Step 4: 写运行手册**

在 README 追加：

```markdown
## 1688 竞店监控

- 前置：租户已登录 1688（work.1688.com 会话有效）。
- 启动 monitor worker：`cd backend/python && python monitor_worker.py --loop --interval-seconds 30`
- 添加监控：1688 模块 → 竞店监控 → 添加店铺监控（店铺链接或商品链接）。
- 排程：`monitor_schedule.interval_minutes`（60/120）自动入队，页面可手动“立即刷新”。
- 告警：`monitor_signal` 表六类信号；`config_json.webhook_url` 配置钉钉/企微 webhook。
- 数据口径：`daily_sales` = 累计销量差值；负增量/异常跳变标记 `suspicious`。
```

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -m "docs(1688-monitor): operation manual and smoke instructions"
```
