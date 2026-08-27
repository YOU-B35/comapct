"""Desktop-window version must stay disabled unless explicitly allowed.

Policy: 桌面版（pywebview 原生窗口）仅在用户明确设置 CROSSHUB_ALLOW_DESKTOP=1
时才能启动；默认（包括生产部署）一律拒绝，避免误弹桌面 UI。
"""
from __future__ import annotations


def test_desktop_mode_refuses_without_allow_flag(monkeypatch, capsys):
    from agent import desktop_app

    monkeypatch.delenv("CROSSHUB_ALLOW_DESKTOP", raising=False)

    code = desktop_app.run_desktop_mode({"bound": False})

    assert code == 2
    captured = capsys.readouterr()
    assert "CROSSHUB_ALLOW_DESKTOP" in (captured.out + captured.err)


def test_desktop_mode_entrypoint_refuses_without_allow_flag(monkeypatch, capsys):
    import sys

    monkeypatch.delenv("CROSSHUB_ALLOW_DESKTOP", raising=False)
    monkeypatch.setattr(sys, "argv", ["sync_helper_desktop.py"])

    from scripts.sync_helper_desktop import main

    code = main()

    assert code == 2
    captured = capsys.readouterr()
    assert "CROSSHUB_ALLOW_DESKTOP" in (captured.out + captured.err)
