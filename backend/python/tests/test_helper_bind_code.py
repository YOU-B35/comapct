"""Helper bind-code enrollment + machine fingerprint (httpx mock)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

PY_ROOT = Path(__file__).resolve().parents[1]
if str(PY_ROOT) not in sys.path:
    sys.path.insert(0, str(PY_ROOT))


def test_machine_fingerprint_non_empty():
    from agent.machine_id import machine_fingerprint

    fp = machine_fingerprint()
    assert isinstance(fp, str)
    assert fp.strip() != ""
    assert len(fp) >= 8


def test_consume_bind_code_posts_snake_case_body_and_persists(tmp_path: Path):
    from agent.bind import consume_bind_code
    from agent.machine_id import machine_fingerprint

    captured: dict = {}
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "agent_token": "tok-from-bind",
                    "tenant_id": 5,
                    "user_id": 42,
                    "java_api_url": "https://www.yoto.work",
                },
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _make_client(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    with patch("agent.bind.httpx.Client", side_effect=_make_client):
        result = consume_bind_code(
            "AbCd1234",
            display_name="测试助手",
            config_path=config_path,
            base_url="https://www.yoto.work",
        )

    assert captured["method"] == "POST"
    assert captured["url"].rstrip("/").endswith("/api/agent/bind")
    body = captured["body"]
    assert set(body.keys()) == {"code", "machine_fingerprint", "display_name"}
    assert body["code"] == "AbCd1234"
    assert body["display_name"] == "测试助手"
    assert body["machine_fingerprint"] == machine_fingerprint()
    # ensure snake_case (no camelCase)
    assert "machineFingerprint" not in body
    assert "displayName" not in body

    assert result["agent_token"] == "tok-from-bind"
    assert result["user_id"] == 42

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["agent_token"] == "tok-from-bind"
    assert saved["java_api_url"] == "https://www.yoto.work"
    assert saved["user_id"] == 42
    assert saved["tenant_id"] == 5
    assert saved["machine_fingerprint"] == machine_fingerprint()


def test_profile_root_includes_user_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import config as app_config

    monkeypatch.delenv("TEMU_PROFILE_ROOT", raising=False)
    monkeypatch.setenv("CROSSHUB_BOUND_USER_ID", "42")
    # Force base under tmp by patching ROOT
    monkeypatch.setattr(app_config, "ROOT", tmp_path)

    root = app_config.resolve_profile_root()
    assert "user-42" in root.parts or root.name == "user-42" or "user-42" in str(root)
