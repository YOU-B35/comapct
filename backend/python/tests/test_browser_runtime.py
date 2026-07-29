import unittest

from app.browser import runtime


class FakeContext:
    def __init__(self, label: str):
        self.label = label
        self.closed = False

    def close(self):
        self.closed = True


class BrowserRuntimeTests(unittest.TestCase):
    def setUp(self):
        runtime.reset_browser_runtime_for_tests()

    def tearDown(self):
        runtime.reset_browser_runtime_for_tests()

    def test_reuses_same_tenant_runtime_without_relaunch(self):
        launches = []

        def launcher(tenant_id: int, headless: bool):
            launches.append((tenant_id, headless))
            return FakeContext(f"tenant-{tenant_id}-{len(launches)}")

        first = runtime.get_or_create_browser_runtime(tenant_id=5, headless=False, launcher=launcher)
        second = runtime.get_or_create_browser_runtime(tenant_id=5, headless=False, launcher=launcher)

        self.assertIs(first.context, second.context)
        self.assertEqual(launches, [(5, False)])

    def test_separates_runtimes_by_tenant(self):
        launches = []

        def launcher(tenant_id: int, headless: bool):
            launches.append((tenant_id, headless))
            return FakeContext(f"tenant-{tenant_id}")

        first = runtime.get_or_create_browser_runtime(tenant_id=5, headless=False, launcher=launcher)
        second = runtime.get_or_create_browser_runtime(tenant_id=6, headless=False, launcher=launcher)

        self.assertIsNot(first.context, second.context)
        self.assertEqual(launches, [(5, False), (6, False)])

    def test_close_runtime_evicts_cached_context(self):
        launches = []

        def launcher(tenant_id: int, headless: bool):
            launches.append((tenant_id, headless))
            return FakeContext(f"tenant-{tenant_id}-{len(launches)}")

        first = runtime.get_or_create_browser_runtime(tenant_id=5, headless=True, launcher=launcher)
        runtime.close_browser_runtime(tenant_id=5)
        second = runtime.get_or_create_browser_runtime(tenant_id=5, headless=True, launcher=launcher)

        self.assertTrue(first.context.closed)
        self.assertIsNot(first.context, second.context)
        self.assertEqual(launches, [(5, True), (5, True)])

    def test_relaunches_stale_runtime_before_reuse(self):
        launches = []

        def launcher(tenant_id: int, headless: bool):
            launches.append((tenant_id, headless))
            return FakeContext(f"tenant-{tenant_id}-{len(launches)}")

        first = runtime.get_or_create_browser_runtime(
            tenant_id=5,
            headless=False,
            launcher=launcher,
            is_usable=lambda context: not context.closed,
        )
        first.context.close()

        second = runtime.get_or_create_browser_runtime(
            tenant_id=5,
            headless=False,
            launcher=launcher,
            is_usable=lambda context: not context.closed,
        )

        self.assertIsNot(first.context, second.context)
        self.assertEqual(launches, [(5, False), (5, False)])


if __name__ == "__main__":
    unittest.main()
