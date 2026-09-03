from pathlib import Path
from unittest.mock import patch

import pytest

from app.ziniao.client import ZiniaoConfig
from app.ziniao.discovery import discover_ziniao_client_path


def test_explicit_existing_path_has_priority(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.exe"
    running = tmp_path / "running.exe"
    explicit.touch()
    running.touch()

    with patch("app.ziniao.discovery._running_ziniao_executables", return_value=[running]):
        assert discover_ziniao_client_path(str(explicit)) == explicit


def test_explicit_missing_path_does_not_fall_back(tmp_path: Path) -> None:
    missing = tmp_path / "missing.exe"

    with pytest.raises(FileNotFoundError, match="ZINIAO_CLIENT_PATH"):
        discover_ziniao_client_path(str(missing))


def test_discovery_prefers_running_client(tmp_path: Path) -> None:
    running = tmp_path / "running.exe"
    registry = tmp_path / "registry.exe"
    common = tmp_path / "common.exe"
    running.touch()
    registry.touch()
    common.touch()

    with patch("app.ziniao.discovery._running_ziniao_executables", return_value=[running]), patch(
        "app.ziniao.discovery._registry_ziniao_executables", return_value=[registry]
    ), patch("app.ziniao.discovery._common_ziniao_executables", return_value=[common]):
        assert discover_ziniao_client_path() == running


def test_discovery_uses_registry_before_common_path(tmp_path: Path) -> None:
    registry = tmp_path / "registry.exe"
    common = tmp_path / "common.exe"
    registry.touch()
    common.touch()

    with patch("app.ziniao.discovery._running_ziniao_executables", return_value=[]), patch(
        "app.ziniao.discovery._registry_ziniao_executables", return_value=[registry]
    ), patch("app.ziniao.discovery._common_ziniao_executables", return_value=[common]):
        assert discover_ziniao_client_path() == registry


def test_discovery_uses_common_path_as_fallback(tmp_path: Path) -> None:
    common = tmp_path / "common.exe"
    common.touch()

    with patch("app.ziniao.discovery._running_ziniao_executables", return_value=[]), patch(
        "app.ziniao.discovery._registry_ziniao_executables", return_value=[]
    ), patch("app.ziniao.discovery._common_ziniao_executables", return_value=[common]):
        assert discover_ziniao_client_path() == common


def test_missing_client_has_actionable_error() -> None:
    with patch("app.ziniao.discovery._running_ziniao_executables", return_value=[]), patch(
        "app.ziniao.discovery._registry_ziniao_executables", return_value=[]
    ), patch("app.ziniao.discovery._common_ziniao_executables", return_value=[]):
        with pytest.raises(FileNotFoundError, match="registry.*ZINIAO_CLIENT_PATH"):
            discover_ziniao_client_path()


def test_config_passes_explicit_client_path_to_discovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    executable = tmp_path / "ziniao.exe"
    executable.touch()
    monkeypatch.setenv("ZINIAO_COMPANY", "company")
    monkeypatch.setenv("ZINIAO_USERNAME", "username")
    monkeypatch.setenv("ZINIAO_PASSWORD", "password")
    monkeypatch.setenv("ZINIAO_CLIENT_PATH", str(executable))

    with patch("app.ziniao.client.discover_ziniao_client_path", return_value=executable) as discover:
        config = ZiniaoConfig.from_env()

    discover.assert_called_once_with(str(executable))
    assert config.client_path == executable
