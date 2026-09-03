from __future__ import annotations

from unittest.mock import patch

import agent.main as agent_main


def test_detect_ziniao_online_uses_cli_when_webdriver_port_is_closed() -> None:
    with patch("agent.main.ziniao_port_open", return_value=False), patch(
        "agent.main.cli_tools.ziniao_doctor", return_value={"ok": True}
    ):
        agent_main._cli_probe_at = 0.0
        assert agent_main.detect_ziniao_online(None) is True


def test_detect_ziniao_online_prefers_webdriver_port() -> None:
    with patch("agent.main.ziniao_port_open", return_value=True):
        assert agent_main.detect_ziniao_online(None) is True
