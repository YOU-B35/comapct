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

# 关闭公告/引导/活动弹窗：只点「关闭/知道了/暂不」类按钮，不执行「去开通/立即体验」等业务操作。
DISMISS_TEMU_OVERLAYS_JS = """() => {
  const CLOSE_RE = /^(×|✕|x|X|关闭|关闭全部|我知道了|知道了|朕知道了|暂不|暂不需要|以后再说|不再提示|跳过|取消)$/;
  const CLOSE_SOFT = /(关闭|我知道了|知道了|暂不|以后再说|跳过|dismiss|close)/i;
  const OPEN_RE = /(立即|去开通|去设置|去查看|马上|开始体验|立即体验|立即开通|去开通服务)/;

  const visible = (el) => {
    if (!el || !el.getBoundingClientRect) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    const st = window.getComputedStyle(el);
    return st && st.visibility !== 'hidden' && st.display !== 'none' && st.opacity !== '0';
  };

  let closed = 0;
  const clickEl = (el) => {
    try {
      el.click();
      closed += 1;
      return true;
    } catch (e) {
      return false;
    }
  };

  const candidates = Array.from(document.querySelectorAll(
    'button, [role="button"], a, span, div, i, svg, [aria-label], [class*="close"], [class*="Close"]'
  ));
  for (const el of candidates) {
    if (!visible(el)) continue;
    const label = (
      (el.getAttribute('aria-label') || '') + ' ' +
      (el.getAttribute('title') || '') + ' ' +
      (el.innerText || el.textContent || '')
    ).replace(/\\s+/g, ' ').trim();
    if (!label) continue;
    if (OPEN_RE.test(label) && !CLOSE_SOFT.test(label)) continue;
    if (CLOSE_RE.test(label) || (label.length <= 8 && CLOSE_SOFT.test(label))) {
      clickEl(el);
    }
  }

  // 仍挡住点击的 dialog / modal / mask：尽量点其内部关闭钮；否则移除遮罩节点
  const overlays = Array.from(document.querySelectorAll(
    '[role="dialog"], [class*="modal"], [class*="Modal"], [class*="dialog"], [class*="Dialog"], [class*="drawer"], [class*="Drawer"], [class*="popover"], [class*="Mask"], [class*="mask"], [class*="overlay"], [class*="Overlay"]'
  ));
  for (const box of overlays) {
    if (!visible(box)) continue;
    const innerBtns = Array.from(box.querySelectorAll('button, [role="button"], [aria-label], [class*="close"]'));
    let hit = false;
    for (const el of innerBtns) {
      const label = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).trim();
      if (OPEN_RE.test(label) && !CLOSE_SOFT.test(label)) continue;
      if (!label || CLOSE_RE.test(label) || CLOSE_SOFT.test(label) || label === '×' || label === '✕') {
        if (clickEl(el)) { hit = true; break; }
      }
    }
    if (!hit) {
      try { box.remove(); closed += 1; } catch (e) {}
    }
  }
  return closed;
}"""


def read_page_text(page: Page) -> str:
    try:
        return page.evaluate("() => (document.body && document.body.innerText) || ''") or ""
    except Exception:
        return ""


def dismiss_temu_ui_blockers(page: Page, *, rounds: int = 2) -> int:
    """Dismiss Temu announcement / onboarding modals without following CTA actions."""
    total = 0
    for _ in range(max(1, rounds)):
        try:
            closed = int(page.evaluate(DISMISS_TEMU_OVERLAYS_JS) or 0)
        except Exception:
            closed = 0
        total += closed
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        if closed <= 0:
            break
        try:
            page.wait_for_timeout(400)
        except Exception:
            pass
    return total


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
    dismiss_temu_ui_blockers(page)
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
    """进入全托管销售管理页；若落在「该区暂无权限」则纠正，无法纠正则抛错。

    策略：直接 goto 官方销售管理 URL（尽量绕过首页弹窗），过程中反复关掉公告/引导弹窗。
    """
    target = (sales_page or TEMU_SALES_PAGE).strip() or TEMU_SALES_PAGE
    dismiss_temu_ui_blockers(page)

    current = (page.url or "").lower()
    text = read_page_text(page)

    need_nav = (
        not looks_like_sales_management(url=current, text=text)
        or is_region_no_permission(text)
        or "mmsos/sales-stock-management" in current
    )
    if need_nav:
        page.goto(target, wait_until="domcontentloaded", timeout=120_000)
        dismiss_temu_ui_blockers(page, rounds=3)

    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        pass

    dismiss_temu_ui_blockers(page)
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
            dismiss_temu_ui_blockers(page)
            text = read_page_text(page)

    if is_region_no_permission(text):
        raise RuntimeError(
            "Temu 当前页面提示「该区暂无权限」。全托管店铺请留在「全球」商家中心，"
            f"并从侧栏进入「销售管理」：{TEMU_SALES_PAGE}。"
            "不要进入美区/欧区 Seller Central（半托管区域），也不要打开旧的 mmsos 销售页。"
        )

    if not looks_like_sales_management(url=page.url or "", text=text):
        # 最后再强制 goto 一次并清弹窗
        page.goto(target, wait_until="domcontentloaded", timeout=120_000)
        dismiss_temu_ui_blockers(page, rounds=3)
        text = read_page_text(page)
        if not looks_like_sales_management(url=page.url or "", text=text):
            raise RuntimeError(
                "未能打开 Temu 全托管「销售管理」页（侧栏路径 stock/fully-mgt/sale-manage）。"
                f"当前 URL：{page.url}"
            )
