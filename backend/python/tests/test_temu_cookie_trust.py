import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from app.browser.temu_cookie_trust import _chrome_expiry_to_unix, temu_login_cookies_alive


_CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _unix_to_chrome_us(unix_ts: float) -> int:
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    return int((dt - _CHROME_EPOCH).total_seconds() * 1_000_000)


def _make_cookies_db(path: Path, rows: list[tuple[str, str, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE cookies (
                host_key TEXT,
                name TEXT,
                expires_utc INTEGER,
                has_expires INTEGER
            )
            """
        )
        conn.executemany(
            "INSERT INTO cookies (host_key, name, expires_utc, has_expires) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


class TemuCookieTrustTests(unittest.TestCase):
    def test_chrome_expiry_roundtrip(self):
        now = time.time()
        chrome = _unix_to_chrome_us(now + 3600)
        got = _chrome_expiry_to_unix(chrome)
        assert got is not None
        self.assertAlmostEqual(got, now + 3600, delta=2)

    def test_alive_when_required_cookies_unexpired(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            db = profile / "Default" / "Network" / "Cookies"
            future = _unix_to_chrome_us(time.time() + 86400 * 30)
            _make_cookies_db(
                db,
                [
                    (".temu.com", "AccessToken", future, 1),
                    (".temu.com", "isLogin", future, 1),
                ],
            )
            with mock.patch(
                "app.browser.temu_cookie_trust.resolve_profile_dir",
                return_value=profile,
            ):
                self.assertTrue(temu_login_cookies_alive(5, "18061740604"))

    def test_false_when_cookies_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            db = profile / "Default" / "Network" / "Cookies"
            past = _unix_to_chrome_us(time.time() - 3600)
            _make_cookies_db(
                db,
                [
                    (".temu.com", "AccessToken", past, 1),
                    (".temu.com", "isLogin", past, 1),
                ],
            )
            with mock.patch(
                "app.browser.temu_cookie_trust.resolve_profile_dir",
                return_value=profile,
            ):
                self.assertFalse(temu_login_cookies_alive(5, "18061740604"))

    def test_false_when_cookie_db_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "empty-profile"
            profile.mkdir()
            with mock.patch(
                "app.browser.temu_cookie_trust.resolve_profile_dir",
                return_value=profile,
            ):
                self.assertFalse(temu_login_cookies_alive(5, "18061740604"))

    def test_session_cookie_counts_as_alive(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            db = profile / "Default" / "Network" / "Cookies"
            future = _unix_to_chrome_us(time.time() + 86400)
            _make_cookies_db(
                db,
                [
                    (".temu.com", "AccessToken", 0, 0),
                    (".temu.com", "isLogin", future, 1),
                ],
            )
            with mock.patch(
                "app.browser.temu_cookie_trust.resolve_profile_dir",
                return_value=profile,
            ):
                self.assertTrue(temu_login_cookies_alive(5, "x"))


class ReadyCacheCookieTrustTests(unittest.TestCase):
    def test_ready_cache_trusted_while_cookies_alive_even_if_old(self):
        from app.browser.profile_lock import read_ready_session_cache, write_session_cache

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            with mock.patch("app.browser.profile_lock.resolve_profile_dir", return_value=profile):
                write_session_cache(
                    5,
                    {
                        "ready": True,
                        "logged_in": True,
                        "requires_auth": False,
                        "mall_id": "m1",
                        "mall_count": 1,
                        "malls": [{"mallId": "m1"}],
                    },
                    session_key="sk",
                )
                # Make cache look 30 days old
                cache_path = profile / ".crosshub-session.json"
                import json

                data = json.loads(cache_path.read_text(encoding="utf-8"))
                data["cached_at"] = time.time() - 30 * 24 * 3600
                cache_path.write_text(json.dumps(data), encoding="utf-8")

                with mock.patch(
                    "app.browser.temu_cookie_trust.temu_login_cookies_alive",
                    return_value=True,
                ):
                    got = read_ready_session_cache(5, session_key="sk")
                self.assertIsNotNone(got)
                self.assertTrue(got.get("ready"))

    def test_ready_cache_rejected_when_cookies_expired(self):
        from app.browser.profile_lock import read_ready_session_cache, write_session_cache

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            with mock.patch("app.browser.profile_lock.resolve_profile_dir", return_value=profile):
                write_session_cache(
                    5,
                    {
                        "ready": True,
                        "logged_in": True,
                        "requires_auth": False,
                        "mall_id": "m1",
                        "mall_count": 1,
                        "malls": [{"mallId": "m1"}],
                    },
                    session_key="sk",
                )
                with mock.patch(
                    "app.browser.temu_cookie_trust.temu_login_cookies_alive",
                    return_value=False,
                ):
                    self.assertIsNone(read_ready_session_cache(5, session_key="sk"))


if __name__ == "__main__":
    unittest.main()
