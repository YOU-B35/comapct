"""Tests for Sync Helper local vs production Java API URL resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PY_ROOT = Path(__file__).resolve().parents[1]
if str(PY_ROOT) not in sys.path:
    sys.path.insert(0, str(PY_ROOT))


def test_allow_local_config_beats_stale_online_env(monkeypatch: pytest.MonkeyPatch):
    from agent.helper_java_url import resolve_java_api_url

    monkeypatch.setenv("JAVA_API_URL", "https://www.yoto.work")
    monkeypatch.delenv("CROSSHUB_ALLOW_LOCAL_JAVA", raising=False)
    cfg = {
        "java_api_url": "http://127.0.0.1:18080",
        "allow_local_java": True,
    }
    api, note = resolve_java_api_url(cfg, env_api="https://www.yoto.work")
    assert api == "http://127.0.0.1:18080"
    assert "ignore env" in note


def test_local_url_without_allow_forced_online(monkeypatch: pytest.MonkeyPatch):
    from agent.helper_java_url import DEFAULT_JAVA_API_URL, resolve_java_api_url

    monkeypatch.delenv("CROSSHUB_ALLOW_LOCAL_JAVA", raising=False)
    monkeypatch.delenv("JAVA_API_URL", raising=False)
    cfg = {"java_api_url": "http://127.0.0.1:18080"}
    api, note = resolve_java_api_url(cfg, env_api="")
    assert api == DEFAULT_JAVA_API_URL
    assert "blocked" in note


def test_env_allow_local_java_flag(monkeypatch: pytest.MonkeyPatch):
    from agent.helper_java_url import resolve_java_api_url

    monkeypatch.setenv("CROSSHUB_ALLOW_LOCAL_JAVA", "1")
    cfg = {"java_api_url": "http://127.0.0.1:18080"}
    api, _ = resolve_java_api_url(cfg, env_api="https://www.yoto.work")
    assert api == "http://127.0.0.1:18080"


def test_default_online_when_empty(monkeypatch: pytest.MonkeyPatch):
    from agent.helper_java_url import DEFAULT_JAVA_API_URL, resolve_java_api_url

    monkeypatch.delenv("CROSSHUB_ALLOW_LOCAL_JAVA", raising=False)
    monkeypatch.delenv("JAVA_API_URL", raising=False)
    api, _ = resolve_java_api_url({}, env_api="")
    assert api == DEFAULT_JAVA_API_URL


def test_java_client_prefers_env_over_module_snapshot(monkeypatch: pytest.MonkeyPatch):
    import agent.config as agent_config
    from agent.java_client import AgentApiClient

    monkeypatch.setattr(agent_config, "JAVA_API_URL", "https://www.yoto.work")
    monkeypatch.setattr(agent_config, "AGENT_TOKEN", "tok")
    monkeypatch.setenv("JAVA_API_URL", "http://127.0.0.1:18080")
    monkeypatch.setenv("AGENT_TOKEN", "tok")
    client = AgentApiClient()
    assert client.base_url == "http://127.0.0.1:18080"
