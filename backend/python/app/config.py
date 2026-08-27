"""爬虫运行配置（可通过环境变量或 .env 覆盖）"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv


def _module_root() -> Path:
    """源码态 = backend/python；冻结态勿用 _internal 当业务根（会新建空 Profile 丢 Cookie）。"""
    if getattr(sys, "frozen", False):
        configured = (os.getenv("CROSSHUB_PROJECT_ROOT") or "").strip()
        if configured:
            return Path(configured) / "backend" / "python"
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in (
            exe_dir / "backend" / "python",
            exe_dir.parent / "backend" / "python",
            Path(r"D:\NIUBI\SaaS-HZ_WEB_Demo\backend\python"),
        ):
            if (candidate / ".temu-browser-profile").is_dir() or (candidate / "app").is_dir():
                return candidate
        return exe_dir
    return Path(__file__).resolve().parents[1]


ROOT = _module_root()
_env_file = ROOT / ".env"
if _env_file.is_file():
    load_dotenv(_env_file, override=False)
elif not getattr(sys, "frozen", False):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _profile_isolation_segment() -> str:
    """Shop isolation lives under tenant-{id}/account-* via session_scope.

    CrossHub user id must NOT nest profile roots (machine-bound tenant helper).
    """
    return ""


def resolve_profile_root() -> Path:
    env = (os.getenv("TEMU_PROFILE_ROOT") or "").strip()
    base = Path(env) if env else (ROOT / ".temu-browser-profile")
    segment = _profile_isolation_segment()
    if segment:
        # Same segment already applied — do not nest again.
        if base.name == segment:
            return base
        # Stale leaf from a previous bind: strip then re-nest under current id.
        if base.name.startswith("user-") or base.name.startswith("account-"):
            base = base.parent
        return base / segment
    # Unbound: do not keep a previous user-*/account-* leaf.
    if base.name.startswith("user-") or base.name.startswith("account-"):
        return base.parent
    return base


def resolve_profile_dir(tenant_id: int, session_key: str | None = None) -> Path:
    """每次调用读环境变量，避免冻结态误用 _internal 空 Profile。

    session_key 按卖家登录账号分组；缺省为 default。
    兼容旧版扁平目录 tenant-{id}（仅在 default 且新目录不存在时使用）。
    """
    from app.session_scope import resolve_platform_profile_dir

    return resolve_platform_profile_dir(
        "temu", tenant_id, session_key, root=resolve_profile_root()
    )


def resolve_tenant_id(cli_value: int | None = None) -> int:
    if cli_value is not None and cli_value > 0:
        return cli_value
    env_value = os.getenv("TENANT_ID", "").strip()
    if env_value.isdigit() and int(env_value) > 0:
        return int(env_value)
    raise ValueError("缺少租户 ID：请传入 --tenant-id 或设置环境变量 TENANT_ID")


# 兼容旧引用（导入瞬间快照；业务请优先用 resolve_profile_dir）
PROFILE_ROOT = resolve_profile_root()

# 默认有头 + 本机 Chrome，降低 Temu 风控识别概率
TEMU_SELLER_HOME = os.getenv("TEMU_SELLER_HOME", "https://agentseller.temu.com/")
TEMU_SALES_API = os.getenv(
    "TEMU_SALES_API",
    "https://agentseller.temu.com/mms/venom/api/supplier/sales/management/listOverall",
)
TEMU_USER_INFO_API = os.getenv(
    "TEMU_USER_INFO_API",
    "https://agentseller.temu.com/api/seller/auth/userInfo",
)
# 全托管「销售管理」官方侧栏入口（fully-mgt）。旧 mmsos 路径对全托管常显示「该区暂无权限」。
TEMU_SALES_PAGE = os.getenv(
    "TEMU_SALES_PAGE",
    "https://agentseller.temu.com/stock/fully-mgt/sale-manage/main",
)
TEMU_SALES_PAGE_LEGACY = os.getenv(
    "TEMU_SALES_PAGE_LEGACY",
    "https://agentseller.temu.com/mmsos/sales-stock-management/sales-management",
)
MALL_STORAGE_KEY = os.getenv("TEMU_MALL_STORAGE_KEY", "agentseller-mall-info-id")


def is_headless() -> bool:
    return os.getenv("TEMU_HEADLESS", "0").strip().lower() in ("1", "true", "yes")


def sync_headless_enabled() -> bool:
    """抖音/PDD 等同步任务是否以无头模式启动（登录任务始终有头，便于交互）。

    环境变量 CROSSHUB_HEADLESS=1 开启；无头模式下若检测到未登录会直接报错，
    不会弹出可交互窗口。
    """
    return os.getenv("CROSSHUB_HEADLESS", "0").strip().lower() in ("1", "true", "yes")


HEADLESS = is_headless()
BROWSER_CHANNEL = os.getenv("TEMU_BROWSER_CHANNEL", "").strip() or None

MIN_ACTION_DELAY_MS = int(os.getenv("TEMU_MIN_DELAY_MS", "800"))
MAX_ACTION_DELAY_MS = int(os.getenv("TEMU_MAX_DELAY_MS", "2200"))
TEMU_LOGIN_WAIT_SECONDS = int(os.getenv("TEMU_LOGIN_WAIT_SECONDS", "240"))
TEMU_LOGIN_POLL_SECONDS = int(os.getenv("TEMU_LOGIN_POLL_SECONDS", "3"))
AMAZON_LOGIN_WAIT_SECONDS = int(os.getenv("AMAZON_LOGIN_WAIT_SECONDS", "180"))
AMAZON_LOGIN_POLL_SECONDS = float(os.getenv("AMAZON_LOGIN_POLL_SECONDS", "5"))
AMAZON_LOGIN_MAX_ATTEMPTS = int(os.getenv("AMAZON_LOGIN_MAX_ATTEMPTS", "3"))

STATUS_TO_CODE = {10: "100", 11: "200", 12: "300", 13: "400"}


def resolve_ae_profile_root() -> Path:
    env = (os.getenv("AE_PROFILE_ROOT") or "").strip()
    base = Path(env) if env else (ROOT / ".aliexpress-browser-profile")
    segment = _profile_isolation_segment()
    if segment:
        if base.name == segment:
            return base
        if base.name.startswith("user-") or base.name.startswith("account-"):
            base = base.parent
        return base / segment
    if base.name.startswith("user-") or base.name.startswith("account-"):
        return base.parent
    return base


AE_PROFILE_ROOT = resolve_ae_profile_root()


def resolve_aliexpress_profile_dir(tenant_id: int, session_key: str | None = None) -> Path:
    """AliExpress Profile：tenant-{id}/account-{session_key}，兼容旧扁平目录。"""
    from app.session_scope import resolve_platform_profile_dir

    return resolve_platform_profile_dir(
        "aliexpress", tenant_id, session_key, root=resolve_ae_profile_root()
    )


AE_CSP_HOME = os.getenv("AE_CSP_HOME", "https://csp.aliexpress.com/")
AE_JIT_ORDER_PAGE = os.getenv(
    "AE_JIT_ORDER_PAGE",
    "https://gsp.aliexpress.com/m_apps/ascp/aechoice.purchase_jit_order_list",
)
AE_WAREHOUSE_ORDER_PAGE = os.getenv(
    "AE_WAREHOUSE_ORDER_PAGE",
    "https://gsp.aliexpress.com/m_apps/ascp/aechoice.purchase_stockup_for_aechoice",
)
AE_JIT_CONSIGN_API = os.getenv(
    "AE_JIT_CONSIGN_API",
    "https://scm-supplier.aliexpress.com/aidc-ib-web-f/purchase/supplier/queryJitConsignOrders",
)
AE_WAREHOUSE_ORDER_API = os.getenv(
    "AE_WAREHOUSE_ORDER_API",
    "https://scm-supplier.aliexpress.com/aidc-procurement/webapi/purchase/queryPurchaseOrders",
)
AE_ORDER_PAGE = os.getenv(
    "AE_ORDER_PAGE",
    "https://csp.aliexpress.com/m_apps/order-manage/orderList",
)
AE_VIOLATION_PAGE = os.getenv(
    "AE_VIOLATION_PAGE",
    "https://gsp.aliexpress.com/m_apps/violation/violist",
)
AE_JIT_PACKAGE_API = os.getenv(
    "AE_JIT_PACKAGE_API",
    "https://scm-supplier.aliexpress.com/dchain-seller-portal-ae/popChoicePackage/queryListV2",
)
AE_ORDER_API = os.getenv(
    "AE_ORDER_API",
    "https://csp.aliexpress.com/api/order/list",
)
AE_VIOLATION_API = os.getenv(
    "AE_VIOLATION_API",
    "https://csp.aliexpress.com/api/violation/list",
)


def is_ae_headless() -> bool:
    return os.getenv("AE_HEADLESS", os.getenv("TEMU_HEADLESS", "0")).strip().lower() in (
        "1",
        "true",
        "yes",
    )


AE_LOGIN_WAIT_SECONDS = int(os.getenv("AE_LOGIN_WAIT_SECONDS", "240"))
AE_LOGIN_POLL_SECONDS = int(os.getenv("AE_LOGIN_POLL_SECONDS", "3"))

# 紫鸟 WebDriver（本地 127.0.0.1，见 open.ziniao.com docId=98）
ZINIAO_COMPANY = os.getenv("ZINIAO_COMPANY", "").strip()
ZINIAO_USERNAME = os.getenv("ZINIAO_USERNAME", "").strip()
ZINIAO_PASSWORD = os.getenv("ZINIAO_PASSWORD", "").strip()
ZINIAO_CLIENT_PATH = os.getenv("ZINIAO_CLIENT_PATH", r"C:\Program Files\ziniao\ziniao.exe").strip()
ZINIAO_SOCKET_PORT = int(os.getenv("ZINIAO_SOCKET_PORT", "16851"))
