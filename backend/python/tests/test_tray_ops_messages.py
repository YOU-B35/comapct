from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent import tray_app


def test_ops_messages_reads_remote_api_instead_of_local_db():
    app = tray_app._build_flask_app(java_client=MagicMock())
    client = app.test_client()

    remote_payload = {
        "data": {
            "items": [
                {
                    "job_id": "amz_sync_1",
                    "platform_account_id": "pa_1",
                    "status": "failed",
                    "store_name": "YOTO美国账号",
                    "account": "yoto_001@163.com",
                    "retry_count": 2,
                    "max_retry_count": 2,
                    "retry_exhausted": True,
                    "failed_at": "2026-07-30 16:58:00",
                    "failure_reason": "任务执行超时",
                }
            ],
            "unread": 1,
        }
    }

    response = MagicMock()
    response.status_code = 200
    response.content = b"ok"
    response.json.return_value = remote_payload

    with patch("agent.tray_app._api_base", return_value="http://remote-java:18080"):
        with patch("agent.tray_app._api_headers", return_value={"X-Agent-Token": "token"}):
            with patch("httpx.get", return_value=response) as mock_get:
                with patch("app.db.connect", side_effect=AssertionError("should not touch local db")):
                    resp = client.get("/api/ops/messages?tenant_id=5")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["unread"] == 1
    assert data["items"][0]["job_id"] == "amz_sync_1"
    mock_get.assert_called_once()
