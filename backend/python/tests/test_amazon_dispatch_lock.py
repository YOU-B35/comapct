from contextlib import nullcontext
import unittest
from unittest.mock import MagicMock, patch

from agent.handlers import dispatch_task


class AmazonDispatchLockTests(unittest.TestCase):
    def _task(self, task_type: str) -> dict:
        return {
            "task_id": "amazon-task-1",
            "task_type": task_type,
            "payload": {"tenant_id": 7, "browser_id": "ziniao-browser-9"},
        }

    def test_sync_holds_browser_identity_lock(self):
        with patch("agent.handlers.BROWSER_LOCK_POOL.guard", return_value=nullcontext()) as guard, \
                patch("agent.handlers.handle_amazon_sync") as handler:
            dispatch_task(MagicMock(), self._task("amazon_sync"))

        handler.assert_called_once()
        guard.assert_called_once_with("amazon", "amazon:7:ziniao-browser-9")

    def test_write_holds_browser_identity_lock(self):
        with patch("agent.handlers.BROWSER_LOCK_POOL.guard", return_value=nullcontext()) as guard, \
                patch("agent.handlers.handle_amazon_write") as handler:
            dispatch_task(MagicMock(), self._task("amazon_write"))

        handler.assert_called_once()
        guard.assert_called_once_with("amazon", "amazon:7:ziniao-browser-9")


if __name__ == "__main__":
    unittest.main()
