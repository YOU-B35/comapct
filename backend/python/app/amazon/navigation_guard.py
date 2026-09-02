"""Seller Central 导航守卫：禁止误点页脚/外链，拒绝 sellermobileapp 等陷阱页。"""
from __future__ import annotations

import re
import time
from typing import Any
BLOCKED_URL_RE = re.compile(
    r"sellermobileapp|/ap/signin|sellercentral\.amazon\.com/gp/help",
    re.I,
)

# 误点页脚「下载卖家 App」等 — 见 docs/amazon-integration/19-SC站点测绘-方法.md

BR_CHILD_HREF_RE = re.compile(
    r"sales-traffic-by-asin|DetailSalesTrafficByChild|按子商品|child.?asin",
    re.I,
)

HEADER_SCOPE_SELECTORS = (
    "header",
    "#sc-nav-bar",
    "kat-header",
    "nav[aria-label]",
)

MAIN_SCOPE_SELECTORS = (
    "kat-workflow",
    "main",
    "#sc-content-container",
    '[role="main"]',
    '[data-testid="report-page"]',
    "div.business-reports",
    "aside nav",
    "kat-side-nav",
    "#left-nav",
)


def wait_for_page_patterns(
    page,
    patterns: tuple[str, ...],
    *,
    timeout_seconds: float,
    poll_seconds: float = 0.25,
) -> str:
    """Wait until a target report is rendered, without a fixed post-goto sleep."""
    compiled = tuple(re.compile(pattern, re.I) for pattern in patterns)
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    latest = ""
    while True:
        try:
            latest = str(page.inner_text("body") or "")
        except Exception:
            latest = ""
        if any(pattern.search(f"{page.url}\n{latest}") for pattern in compiled):
            return latest
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return latest
        delay = min(max(0.05, poll_seconds), remaining)
        try:
            page.wait_for_timeout(max(1, int(delay * 1000)))
        except Exception:
            time.sleep(delay)


def is_blocked_url(url: str) -> bool:
    return bool(BLOCKED_URL_RE.search(url or ""))


def assert_allowed_url(url: str, *, context: str = "") -> None:
    if is_blocked_url(url):
        raise RuntimeError(f"导航进入禁止页面 {url!r} ({context})")


def _main_scope_js() -> str:
    selectors = ", ".join(MAIN_SCOPE_SELECTORS)
    return f"""
    () => {{
      const blocked = (node) => {{
        if (!node) return true;
        const footer = document.querySelector('footer, [class*="footer"], [id*="footer"]');
        if (footer && footer.contains(node)) return true;
        const href = (node.getAttribute?.('href') || node.href || '').toLowerCase();
        if (/sellermobileapp|seller-mobile|mobileapp/i.test(href)) return true;
        return false;
      }};
      for (const sel of [{", ".join(repr(s) for s in MAIN_SCOPE_SELECTORS)}]) {{
        const el = document.querySelector(sel);
        if (el) return {{ root: el, label: sel }};
      }}
      return {{ root: document.body, label: 'body' }};
    }}
    """


def click_scoped(page, pattern: str, *, kinds: str = "button, kat-button, kat-tab, [role='tab']") -> bool:
    """仅在主内容/侧栏内点击，排除页脚与 sellermobileapp 链接。"""
    return _click_in_scopes(page, pattern, kinds=kinds, scope_selectors=MAIN_SCOPE_SELECTORS)


def click_header_scoped(page, pattern: str, *, kinds: str = "a, kat-tab, [role='tab'], button") -> bool:
    """顶栏/主导航内点击（业务报告等），排除页脚。"""
    return _click_in_scopes(page, pattern, kinds=kinds, scope_selectors=HEADER_SCOPE_SELECTORS)


def _click_in_scopes(page, pattern: str, *, kinds: str, scope_selectors: tuple[str, ...]) -> bool:
    return bool(
        page.evaluate(
            f"""
            () => {{
              const blocked = (node) => {{
                if (!node) return true;
                const footer = document.querySelector('footer, [class*="footer"], [id*="footer"]');
                if (footer && footer.contains(node)) return true;
                const href = (node.getAttribute?.('href') || node.href || '').toLowerCase();
                if (/sellermobileapp|seller-mobile|mobileapp/i.test(href)) return true;
                return false;
              }};
              let root = null;
              for (const sel of [{", ".join(repr(s) for s in scope_selectors)}]) {{
                const el = document.querySelector(sel);
                if (el) {{ root = el; break; }}
              }}
              if (!root) root = document.body;
              const re = new RegExp({pattern!r}, 'i');
              const nodes = [...root.querySelectorAll({kinds!r})];
              const target = nodes.find((node) => {{
                if (blocked(node)) return false;
                const text = (node.innerText || node.getAttribute('label') || node.getAttribute('aria-label') || node.value || '').trim();
                return re.test(text);
              }});
              if (!target) return false;
              target.click();
              return true;
            }}
            """
        )
    )


def navigate_to_br_child_asin(page, *, home_url: str) -> str:
    """经测绘验证：直连 BR 子 ASIN 报表 hash；侧栏仅作 fallback。"""
    from app.amazon.page_urls import BR_CHILD_REPORT_URL, BR_DASHBOARD_URL, REPORT_URLS

    page.goto(BR_CHILD_REPORT_URL, wait_until="domcontentloaded")
    body = wait_for_page_patterns(
        page,
        (r"DetailSalesTrafficByChild", r"按子商品", r"child.?asin"),
        timeout_seconds=6,
    )
    assert_allowed_url(page.url, context="br_child_direct")
    if is_blocked_url(page.url):
        raise RuntimeError(f"BR 直连落入禁止页: {page.url}")

    if not re.search(r"DetailSalesTrafficByChild|按子商品", f"{page.url}{body[:800]}", re.I):
        navigate_br_child_asin_via_sidebar(page)
        body = wait_for_page_patterns(
            page,
            (r"DetailSalesTrafficByChild", r"按子商品", r"child.?asin"),
            timeout_seconds=5,
        )

    if "#/dashboard" in (page.url or "") and not re.search(r"DetailSalesTrafficByChild", page.url, re.I):
        page.goto(REPORT_URLS[1], wait_until="domcontentloaded")
        wait_for_page_patterns(
            page,
            (r"业务报告", r"business reports", r"DetailSalesTrafficByChild"),
            timeout_seconds=4,
        )
        navigate_br_child_asin_via_sidebar(page)
        body = wait_for_page_patterns(
            page,
            (r"DetailSalesTrafficByChild", r"按子商品", r"child.?asin"),
            timeout_seconds=5,
        )

    if "#/dashboard" in (page.url or ""):
        page.goto(BR_DASHBOARD_URL, wait_until="domcontentloaded")
        wait_for_page_patterns(
            page,
            (r"业务报告", r"business reports", r"DetailSalesTrafficByChild"),
            timeout_seconds=3,
        )
        navigate_br_child_asin_via_sidebar(page)
        wait_for_page_patterns(
            page,
            (r"DetailSalesTrafficByChild", r"按子商品", r"child.?asin"),
            timeout_seconds=5,
        )

    assert_allowed_url(page.url, context="br_nav_child_asin")
    return page.url


def navigate_br_child_asin_via_sidebar(page) -> str:
    """从侧栏业务报告菜单进入「子 ASIN 详情页流量」，返回点击的 href。"""
    href = page.evaluate(
        """
        () => {
          const blocked = (href) => /sellermobileapp|mobileapp/i.test(href || '');
          const scopes = document.querySelectorAll('aside, kat-side-nav, nav, [class*="sidebar"], [class*="SideNav"]');
          const roots = scopes.length ? [...scopes] : [document.body];
          const patterns = [
            /DetailSalesTrafficByChildItem/i,
            /按子商品/i,
            /child.?asin/i,
            /sales-traffic-by-asin/i,
            /detail page sales and traffic by child/i,
            /详情页面销售和流量.*子/i,
          ];
          for (const root of roots) {
            const links = [...root.querySelectorAll('a[href]')];
            for (const link of links) {
              const href = link.getAttribute('href') || '';
              const text = (link.innerText || '').trim();
              if (blocked(href)) continue;
              if (patterns.some((p) => p.test(href) || p.test(text))) {
                link.click();
                return href;
              }
            }
          }
          return '';
        }
        """
    )
    return str(href or "")


def collect_nav_links(page) -> list[dict[str, Any]]:
    """采集顶栏/侧栏链接（排除页脚），供站点测绘。"""
    raw = page.evaluate(
        """
        () => {
          const out = [];
          const seen = new Set();
          const blocked = (href) => /sellermobileapp|mobileapp|javascript:/i.test(href || '');
          const roots = [
            ...document.querySelectorAll('header nav, aside, kat-side-nav, nav[aria-label], #sc-nav-bar, #left-nav'),
          ];
          if (!roots.length) roots.push(document.body);
          for (const root of roots) {
            for (const a of root.querySelectorAll('a[href]')) {
              const footer = document.querySelector('footer, [class*="footer"]');
              if (footer && footer.contains(a)) continue;
              const href = a.href || a.getAttribute('href') || '';
              if (!href || blocked(href) || seen.has(href)) continue;
              seen.add(href);
              out.push({
                text: (a.innerText || '').trim().slice(0, 120),
                href,
                area: root.tagName + (root.id ? '#' + root.id : ''),
              });
            }
          }
          return out;
        }
        """
    )
    return raw if isinstance(raw, list) else []


def attach_network_logger(page, log_path: str) -> None:
    """记录 BR / 报表相关 XHR，供后续对接 API。"""
    patterns = re.compile(r"business-reports|sales-traffic|reporting|GetReport|download", re.I)

    def _on_response(response) -> None:
        try:
            url = response.url or ""
            if not patterns.search(url):
                return
            entry = {
                "url": url,
                "status": response.status,
                "method": response.request.method,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                import json

                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    page.on("response", _on_response)
