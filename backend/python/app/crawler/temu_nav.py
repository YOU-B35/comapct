"""Temu agentseller 页面导航守卫（全托管销售管理）。"""
from __future__ import annotations

from playwright.sync_api import Page

from app.config import TEMU_SALES_PAGE

# 首页「欢迎来到 Seller central」里的美区/欧区，或误进旧 mmsos 路径时常见文案
REGION_NO_PERM_MARKERS = (
    "该区暂无权限",
    "暂无访问权限",
)

SALES_UI_MARKERS = (
    "销售管理",
    "建议备货",
    "今日",
    "近7天",
    "SKU",
    "SKC",
    "在售",
)


def read_page_text(page: Page) -> str:
    try:
        return page.evaluate("() => (document.body && document.body.innerText) || ''") or ""
    except Exception:
        return ""


def is_region_no_permission(text: str) -> bool:
    body = text or ""
    return any(marker in body for marker in REGION_NO_PERM_MARKERS)


def looks_like_sales_management(*, url: str, text: str) -> bool:
    if is_region_no_permission(text):
        return False
    url_l = (url or "").lower()
    on_sales_path = (
        "fully-mgt/sale-manage" in url_l
        or "sale-manage/main" in url_l
        or "sales-management" in url_l
        or "sale-manage" in url_l
    )
    if not on_sales_path:
        return False
    return any(marker in (text or "") for marker in SALES_UI_MARKERS)


def click_sidebar_sales_management(page: Page) -> bool:
    """优先点侧栏官方全托管「销售管理」链接。"""
    try:
        return bool(
            page.evaluate(
                """() => {
                  const anchors = Array.from(document.querySelectorAll('a[href]'));
                  const preferred = anchors.find(a =>
                    (a.href || '').includes('/stock/fully-mgt/sale-manage')
                  );
                  if (preferred) {
                    preferred.click();
                    return true;
                  }
                  const byText = anchors.find(a =>
                    ((a.innerText || '').trim() === '销售管理') &&
                    (a.href || '').includes('sale-manage')
                  );
                  if (byText) {
                    byText.click();
                    return true;
                  }
                  return false;
                }"""
            )
        )
    except Exception:
        return False


def ensure_fully_managed_sales_page(page: Page, *, sales_page: str = TEMU_SALES_PAGE) -> None:
    """进入全托管销售管理页；若落在「该区暂无权限」则纠正，无法纠正则抛错。"""
    target = (sales_page or TEMU_SALES_PAGE).strip() or TEMU_SALES_PAGE
    current = (page.url or "").lower()
    text = read_page_text(page)

    need_nav = (
        not looks_like_sales_management(url=current, text=text)
        or is_region_no_permission(text)
        or "mmsos/sales-stock-management" in current
    )
    if need_nav:
        page.goto(target, wait_until="domcontentloaded", timeout=120_000)

    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        pass

    text = read_page_text(page)
    if looks_like_sales_management(url=page.url or "", text=text):
        return

    if is_region_no_permission(text) or not looks_like_sales_management(
        url=page.url or "", text=text
    ):
        if click_sidebar_sales_management(page):
            try:
                page.wait_for_load_state("domcontentloaded", timeout=30_000)
            except Exception:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            text = read_page_text(page)

    if is_region_no_permission(text):
        raise RuntimeError(
            "Temu 当前页面提示「该区暂无权限」。全托管店铺请留在「全球」商家中心，"
            f"并从侧栏进入「销售管理」：{TEMU_SALES_PAGE}。"
            "不要进入美区/欧区 Seller Central（半托管区域），也不要打开旧的 mmsos 销售页。"
        )

    if not looks_like_sales_management(url=page.url or "", text=text):
        raise RuntimeError(
            "未能打开 Temu 全托管「销售管理」页（侧栏路径 stock/fully-mgt/sale-manage）。"
            f"当前 URL：{page.url}"
        )
