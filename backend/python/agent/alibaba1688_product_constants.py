"""Frozen 1688 product XHR constants. Filled from Day0 probes 2026-08-17."""
from __future__ import annotations

# Live sync enabled: list is manage_mini.vm (SPA may show slide captcha — Helper waits).
PRODUCTS_XHR_READY = True

PRODUCT_HOME_URL = (
    "https://offer.1688.com/app/pages-group/manage-home/index.html"
)
PRODUCT_MANAGE_SPA = PRODUCT_HOME_URL
YANXUAN_HOME_URL = (
    "https://work.1688.com/?_path_=sellerPro/changhuotong/shangpinchengzhang"
)
OPPORTUNITY_HOME_URL = (
    "https://work.1688.com/?_path_=sellerPro/2017sellerbase_offer/opportunity_goods_post"
)

# manage_mini.vm query: lifePeriod = lifecycle tab; growth filters via SPA growthStage.
# list_path: items
LIST_XHR: dict = {
    "all": {
        "on_sale": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=all&lifecycle=valid",
            "life_period": "valid",
            "list_path": "items",
            "page_size": 20,
        },
        "sold_out": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=all&lifecycle=sellOut",
            "life_period": "sellOut",
            "list_path": "items",
            "page_size": 20,
        },
        "pending_list": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=all&lifecycle=expired",
            "life_period": "expired",
            "list_path": "items",
            "page_size": 20,
        },
        "reviewing": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=all&lifecycle=auditing",
            "life_period": "auditing",
            "list_path": "items",
            "page_size": 20,
        },
        "violation_off": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=all&lifecycle=untread",
            "life_period": "untread",
            "list_path": "items",
            "page_size": 20,
        },
        "draft": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=all&lifecycle=draft",
            "life_period": "draft",
            "list_path": "items",
            "page_size": 20,
        },
    },
    "potential": {
        "on_sale": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=qlsp&lifecycle=valid",
            "life_period": "valid",
            "list_path": "items",
            "page_size": 20,
        },
    },
    "index4": {
        "on_sale": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=cgzsspyjg&lifecycle=valid",
            "life_period": "valid",
            "list_path": "items",
            "page_size": 20,
        },
    },
    "yanxuan": {
        "on_sale": {
            "method": "GET",
            "spa": f"{PRODUCT_HOME_URL}?growthStage=growthyxp&lifecycle=valid",
            "life_period": "valid",
            "list_path": "items",
            "page_size": 20,
        },
    },
}

# lifePeriod / growthStage codes from mtop.1688.offermanage.growth.querygrowthlifeperiod
STATUS_MAP: dict[str, str] = {
    "valid": "on_sale",
    "sellOut": "sold_out",
    "expired": "pending_list",
    "auditing": "reviewing",
    "untread": "violation_off",
    "draft": "draft",
    "published": "on_sale",
    "all": "all",
}


def assert_products_xhr_ready() -> None:
    if not PRODUCTS_XHR_READY or not PRODUCT_HOME_URL or not LIST_XHR:
        raise RuntimeError("A1688_PRODUCTS_NEED_DAY0: 1688 商品 XHR 未完成 Day0，禁止 live 同步")
