from __future__ import annotations

from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from app.timezone import load_shanghai_timezone


class ShanghaiTimezoneTests(unittest.TestCase):
    def test_falls_back_to_utc8_without_iana_database(self) -> None:
        with patch("app.timezone.ZoneInfo", side_effect=ZoneInfoNotFoundError("missing")):
            fallback = load_shanghai_timezone()

        self.assertEqual(
            datetime(2026, 1, 1, tzinfo=fallback).utcoffset(),
            timedelta(hours=8),
        )
