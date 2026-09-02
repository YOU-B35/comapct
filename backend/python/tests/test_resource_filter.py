from __future__ import annotations

import unittest
from unittest.mock import patch

from app.browser.resource_filter import install_heavy_resource_filter


class FakeRequest:
    def __init__(self, resource_type: str) -> None:
        self.resource_type = resource_type


class FakeRoute:
    def __init__(self, resource_type: str) -> None:
        self.request = FakeRequest(resource_type)
        self.action = ""

    def abort(self) -> None:
        self.action = "abort"

    def continue_(self) -> None:
        self.action = "continue"


class FakeContext:
    def __init__(self) -> None:
        self.pattern = ""
        self.handler = None

    def route(self, pattern, handler) -> None:
        self.pattern = pattern
        self.handler = handler


class ResourceFilterTest(unittest.TestCase):
    def test_filter_is_disabled_by_default(self) -> None:
        context = FakeContext()
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(install_heavy_resource_filter(context, headless=True))

    def test_headless_filter_blocks_only_heavy_resources(self) -> None:
        context = FakeContext()
        with patch.dict("os.environ", {"CRAWL_BLOCK_HEAVY_RESOURCES": "1"}, clear=False):
            self.assertTrue(install_heavy_resource_filter(context, headless=True))

        image = FakeRoute("image")
        xhr = FakeRoute("xhr")
        context.handler(image)
        context.handler(xhr)

        self.assertEqual(context.pattern, "**/*")
        self.assertEqual(image.action, "abort")
        self.assertEqual(xhr.action, "continue")

    def test_headed_context_does_not_install_filter(self) -> None:
        context = FakeContext()
        self.assertFalse(install_heavy_resource_filter(context, headless=False))
        self.assertIsNone(context.handler)


if __name__ == "__main__":
    unittest.main()
