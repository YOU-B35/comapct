"""系统托盘图标（pystray）。"""
from __future__ import annotations

import threading
import webbrowser
from typing import Callable

WEB_URL = "http://127.0.0.1:19090"


def _create_icon_image():
    """生成一个简易托盘图标（蓝色方块带 C 字）。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (64, 64), (30, 120, 220, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 8), "C", fill="white", font=font)
    return img


def start_tray(on_quit: Callable[[], None]) -> threading.Thread:
    """启动系统托盘，返回托盘线程。"""
    import pystray

    def _open_panel(icon, item):
        webbrowser.open(WEB_URL)

    def _quit(icon, item):
        icon.stop()
        on_quit()

    icon = pystray.Icon(
        "CrossHub Helper",
        _create_icon_image(),
        "CrossHub Sync Helper",
        menu=pystray.Menu(
            pystray.MenuItem("打开面板", _open_panel, default=True),
            pystray.MenuItem("退出", _quit),
        ),
    )

    t = threading.Thread(target=icon.run, daemon=True, name="tray")
    t.start()
    return t
