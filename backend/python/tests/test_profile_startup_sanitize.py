"""sanitize_profile_startup_for_temu clears session restore and pins Temu URL."""
from __future__ import annotations

import json
from pathlib import Path

from app.browser.profile_startup import sanitize_profile_startup_for_temu


def test_sanitize_profile_startup_for_temu_clears_sessions_and_pins_url(tmp_path: Path):
    default = tmp_path / "Default"
    default.mkdir(parents=True)
    (default / "Current Session").write_text("junk", encoding="utf-8")
    sessions = default / "Sessions"
    sessions.mkdir()
    (sessions / "Tabs_1").write_bytes(b"https://www.dianxiaomi.com/login")
    prefs = {
        "session": {"restore_on_startup": 1, "startup_urls": ["https://www.dianxiaomi.com/"]},
        "profile": {"exit_type": "Crashed"},
    }
    (default / "Preferences").write_text(json.dumps(prefs), encoding="utf-8")

    sanitize_profile_startup_for_temu(tmp_path, home_url="https://agentseller.temu.com/")

    assert not (default / "Current Session").exists()
    assert not (sessions / "Tabs_1").exists()
    data = json.loads((default / "Preferences").read_text(encoding="utf-8"))
    assert data["session"]["restore_on_startup"] == 4
    assert data["session"]["startup_urls"] == ["https://agentseller.temu.com/"]
    assert data["profile"]["exit_type"] == "Normal"
