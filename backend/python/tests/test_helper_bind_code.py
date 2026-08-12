"""Helper bind-code enrollment + machine fingerprint (httpx mock)."""

from __future__ import annotations

import json
import os
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
    assert result["java_api_url"] == "https://www.yoto.work"

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["agent_token"] == "tok-from-bind"
    assert saved["java_api_url"] == "https://www.yoto.work"
    assert saved["user_id"] == 42
    assert saved["tenant_id"] == 5
    assert saved["machine_fingerprint"] == machine_fingerprint()


def test_consume_bind_code_keeps_request_api_not_server_payload(tmp_path: Path):
    """Local Java may echo prod java_api_url; Helper must keep the URL it called."""
    from agent.bind import consume_bind_code

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("http://127.0.0.1:18080/")
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "agent_token": "tok-local",
                    "tenant_id": 5,
                    "user_id": 56,
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
            "LocalCode",
            display_name="本机",
            config_path=config_path,
            base_url="http://127.0.0.1:18080",
        )

    assert result["java_api_url"] == "http://127.0.0.1:18080"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["java_api_url"] == "http://127.0.0.1:18080"
    assert saved["agent_token"] == "tok-local"


def test_profile_root_ignores_user_isolation_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import config as app_config

    monkeypatch.delenv("TEMU_PROFILE_ROOT", raising=False)
    monkeypatch.setenv("CROSSHUB_BOUND_USER_ID", "42")
    monkeypatch.setattr(app_config, "ROOT", tmp_path)

    root = app_config.resolve_profile_root()
    assert root == tmp_path / ".temu-browser-profile"
    assert "user-42" not in root.parts


def test_default_config_path_matches_sync_helper_app_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tray GET/status and POST/DELETE must share the same config.json location."""
    import types

    from agent import bind as bind_mod

    fake_sha = types.SimpleNamespace(app_dir=lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "sync_helper_app", fake_sha)
    monkeypatch.delenv("CROSSHUB_HELPER_CONFIG", raising=False)

    path = bind_mod.default_config_path()
    assert path == tmp_path / "config.json"
    assert bind_mod.resolve_config_path() == path
    assert bind_mod.binding_status(config_path=None)["config_path"] == str(path)


def test_clear_binding_resets_sticky_profile_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from agent import bind as bind_mod
    from app import config as app_config

    base = tmp_path / ".temu-browser-profile"
    stale = base / "user-1"
    ae_base = tmp_path / ".aliexpress-browser-profile"
    ae_stale = ae_base / "user-1"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"agent_token": "tok", "user_id": 1, "tenant_id": 9}),
        encoding="utf-8",
    )

    monkeypatch.setenv("TEMU_PROFILE_ROOT", str(stale))
    monkeypatch.setenv("AE_PROFILE_ROOT", str(ae_stale))
    monkeypatch.setenv("CROSSHUB_BOUND_USER_ID", "1")
    monkeypatch.setenv("AGENT_TOKEN", "tok")
    monkeypatch.setattr(app_config, "ROOT", tmp_path)
    app_config.PROFILE_ROOT = stale
    app_config.AE_PROFILE_ROOT = ae_stale

    result = bind_mod.clear_binding(config_path=config_path)
    assert result["ok"] is True

    assert Path(os.environ["TEMU_PROFILE_ROOT"]) == base
    assert Path(os.environ["AE_PROFILE_ROOT"]) == ae_base
    assert "CROSSHUB_BOUND_USER_ID" not in os.environ
    assert app_config.PROFILE_ROOT == base
    assert app_config.AE_PROFILE_ROOT == ae_base


def test_rebind_strips_stale_user_profile_leaf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """After clear/rebind, profile root must not stick on a stale user-* leaf."""
    from agent import bind as bind_mod
    from app import config as app_config

    base = tmp_path / ".temu-browser-profile"
    monkeypatch.setenv("TEMU_PROFILE_ROOT", str(base / "user-1"))
    monkeypatch.delenv("AE_PROFILE_ROOT", raising=False)
    monkeypatch.delenv("CROSSHUB_BOUND_USER_ID", raising=False)
    monkeypatch.delenv("AGENT_USER_ID", raising=False)
    monkeypatch.setattr(app_config, "ROOT", tmp_path)

    bind_mod.reset_profile_roots()
    monkeypatch.setenv("CROSSHUB_BOUND_USER_ID", "99")
    bind_mod.apply_profile_isolation_env()

    root = Path(os.environ["TEMU_PROFILE_ROOT"])
    assert root == base
    assert "user-1" not in root.parts
    assert "user-99" not in root.parts
