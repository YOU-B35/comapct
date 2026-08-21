"""Pure helpers for 1688 shop monitoring (no browser/DB dependencies)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_SHOP_HOST = re.compile(r"^shop[a-z0-9]+\.1688\.com$", re.IGNORECASE)
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
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万)?\+?\s*件?", raw)
    if not m:
        return 0
    num = float(m.group(1))
    if m.lastindex and m.group(2):
        num *= 10000
    return int(num)


def parse_price(text: str | None) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)", str(text or ""))
    return float(m.group(1)) if m else 0.0
