"""运营爬取适配器注册表。"""
from __future__ import annotations

from app.platforms.aliexpress_operational_adapter import AliExpressOperationalAdapter
from app.platforms.alibaba1688_operational_adapter import Alibaba1688OperationalAdapter
from app.platforms.operational_base import PlatformOperationalAdapter
from app.platforms.temu_operational_adapter import TemuOperationalAdapter

_ADAPTERS: dict[str, PlatformOperationalAdapter] = {
    "temu": TemuOperationalAdapter(),
    "aliexpress": AliExpressOperationalAdapter(),
    "1688": Alibaba1688OperationalAdapter(),
}


def get_operational_adapter(platform: str) -> PlatformOperationalAdapter:
    key = str(platform or "").strip().lower()
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        supported = ", ".join(sorted(_ADAPTERS))
        raise ValueError(f"不支持的平台: {platform}，可选: {supported}")
    return adapter


def supported_platforms() -> list[str]:
    return sorted(_ADAPTERS)
