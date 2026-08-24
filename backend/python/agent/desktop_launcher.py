"""Shared desktop launcher logic for CrossHub Sync Helper.

Consolidates common startup logic used by:
  - sync_helper_desktop.py (desktop window mode)
  - desktop_app.py (legacy desktop app variant)
  - _run_desktop_preview.py (UI preview mode)
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def setup_logging(project_root: str = "", debug: bool = False) -> None:
    """Configure structured logging with optional file output."""
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(fmt))
    logging.basicConfig(level=level, handlers=[console])

    # File handler (if project_root provided)
    if project_root:
        log_dir = Path(project_root) / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "sync_helper.log"
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(fmt))
            logging.getLogger().addHandler(file_handler)
            logger.info(f"Logging to {log_file}")
        except Exception as e:
            logger.warning(f"Could not create log file {log_file}: {e}")


def launch_desktop_window(
    client: Any,
    stop_event: threading.Event,
    panel_port: int = 18766,
    on_closed: Callable[[], None] | None = None,
) -> int:
    """
    Launch desktop window via pywebview (with browser fallback).

    Returns:
        0 if clean exit, 1 if pywebview not available
    """
    url = f"http://127.0.0.1:{panel_port}/"

    # Check pywebview availability
    try:
        import webview

        has_webview = True
    except ImportError:
        has_webview = False
        logger.warning("pywebview not installed; will fall back to browser")

    if not has_webview:
        logger.info(f"Opening in browser: {url}")
        webbrowser.open(url)
        stop_event.wait()
        return 0

    # Try pywebview with graceful degradation
    try:
        logger.info("Launching pywebview desktop window")
        time.sleep(1.5)  # Let Flask/services start

        def _on_closed():
            logger.info("Window closed")
            stop_event.set()
            if on_closed:
                on_closed()

        window = webview.create_window(
            title="CrossHub Sync Helper — 跨平台电商同步助手",
            url=url,
            width=1360,
            height=860,
            min_size=(960, 600),
            confirm_close=True,
            text_select=True,
        )
        window.events.closing += _on_closed

        try:
            webview.start(debug=False, func=None)
        except Exception as e:
            logger.error(f"pywebview failed: {e}")
            logger.info("Falling back to browser")
            webbrowser.open(url)
            stop_event.wait()

        return 0
    except ImportError:
        logger.error("pywebview missing at runtime (Edge WebView2 may not be installed)")
        logger.info("Opening in browser: {url}")
        webbrowser.open(url)
        stop_event.wait()
        return 0
    except Exception as e:
        logger.exception(f"Unexpected error in desktop mode: {e}")
        logger.info("Falling back to browser")
        webbrowser.open(url)
        stop_event.wait()
        return 1


def ensure_pythonpath(python_root: Path | None = None) -> None:
    """Ensure backend/python is in sys.path (for frozen and dev mode)."""
    if python_root is None:
        python_root = Path(__file__).resolve().parents[1]  # backend/python

    rs = str(python_root)
    if rs not in sys.path:
        sys.path.insert(0, rs)
    os.environ.setdefault("PYTHONPATH", rs)
    logger.debug(f"PYTHONPATH set to {rs}")


def load_config_with_env(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Overlay environment variables onto config dict.

    Supports:
      - JAVA_API_URL
      - AGENT_TOKEN
      - SSH_HOST (for deploy scripts)
      - DEBUG (enables debug logging)
    """
    cfg = dict(config_dict)  # Copy to avoid mutation

    env_overrides = {
        "java_api_url": "JAVA_API_URL",
        "agent_token": "AGENT_TOKEN",
        "debug": "DEBUG",
    }
    for cfg_key, env_key in env_overrides.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val

    return cfg


def validate_and_prepare_config(
    cfg: dict[str, Any],
) -> tuple[bool, str]:
    """
    Validate config dict and log status.

    Returns:
        (is_bound, status_msg)
    """
    bound = cfg.get("bound", False)
    token = (cfg.get("agent_token") or "").strip()
    api_url = cfg.get("java_api_url", "").strip()

    if bound and token and api_url:
        logger.info(f"Bound to {api_url}")
        return True, "已绑定"

    logger.info("Not bound; Agent polling disabled. Login in panel to bind.")
    return False, "未绑定"


def configure_ssl_warnings() -> None:
    """Suppress urllib3 SSL warnings in development."""
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        pass


def redirect_console_to_log(log_file: Path | None = None) -> None:
    """When running as pythonw, redirect stdout/stderr to log file.

    This ensures that all print() statements and errors are captured
    even when there's no console window attached.
    """
    if log_file is None:
        return

    try:
        import sys
        log_file.parent.mkdir(exist_ok=True, parents=True)

        # Open log file in append mode
        log_fd = open(log_file, "a", encoding="utf-8")

        # Redirect stdout and stderr
        sys.stdout = log_fd
        sys.stderr = log_fd

        # Write startup marker
        print(f"\n{'='*60}")
        print(f"CrossHub Helper started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python: {sys.executable}")
        print(f"{'='*60}\n")
        sys.stdout.flush()
    except Exception as e:
        # If redirection fails, just continue with normal behavior
        logger.warning(f"Could not redirect console to log: {e}")



__all__ = [
    "setup_logging",
    "launch_desktop_window",
    "ensure_pythonpath",
    "load_config_with_env",
    "configure_ssl_warnings",
    "redirect_console_to_log",
]

