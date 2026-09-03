from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agent.handlers import handle_ziniao_discover


class ZiniaoCliDiscoveryFallbackTests(unittest.TestCase):
    def test_cli_discovers_stores_without_legacy_webdriver_credentials(self) -> None:
        client = MagicMock()
        task = {"task_id": "discover-cli-only-1"}

        with patch(
            "agent.handlers.ZiniaoConfig.from_env",
            side_effect=ValueError("请在 backend/python/.env 配置 ZINIAO_COMPANY、ZINIAO_USERNAME、ZINIAO_PASSWORD"),
        ), patch("app.ziniao.cli_tools.ziniao_store_list", return_value={
            "ok": True,
            "data": [{"storeId": "cli-amz-2", "storeName": "Amazon UK", "platformName": "Amazon"}],
        }):
            handle_ziniao_discover(client, task)

        client.complete_task.assert_called_once_with(
            "discover-cli-only-1",
            status="success",
            result={
                "stores": [{
                    "browserId": "",
                    "ziniaoStoreId": "cli-amz-2",
                    "browserName": "Amazon UK",
                    "platformName": "Amazon",
                    "storeUsername": "",
                    "browserIp": "",
                }],
                "transport": "ziniao_cli",
            },
        )

    def test_normal_mode_discovers_amazon_candidates_through_cli(self) -> None:
        client = MagicMock()
        task = {"task_id": "discover-1"}
        webdriver = MagicMock()
        webdriver.ensure_webdriver_client.side_effect = RuntimeError(
            "检测到紫鸟正在普通模式运行（无 WebDriver API）"
        )

        with patch("agent.handlers.ZiniaoConfig.from_env", return_value=MagicMock()), \
                patch("agent.handlers.ZiniaoClient", return_value=webdriver), \
                patch("app.ziniao.cli_tools.ziniao_store_list", return_value={
                    "ok": True,
                    "data": [
                        {"storeId": "cli-amz-1", "storeName": "Amazon US", "platformName": "Amazon"},
                        {"storeId": "cli-pdd-1", "storeName": "PDD", "platformName": "拼多多"},
                    ],
                }):
            handle_ziniao_discover(client, task)

        client.complete_task.assert_called_once_with(
            "discover-1",
            status="success",
            result={
                "stores": [{
                    "browserId": "",
                    "ziniaoStoreId": "cli-amz-1",
                    "browserName": "Amazon US",
                    "platformName": "Amazon",
                    "storeUsername": "",
                    "browserIp": "",
                }],
                "transport": "ziniao_cli",
            },
        )
