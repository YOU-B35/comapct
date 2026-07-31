from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.browser.profile_sync import pull_profile_if_needed


def test_pull_profile_skips_when_local_sha_matches(tmp_path) -> None:
    client = MagicMock()
    client.resolve_agent_tenant_id.return_value = 5
    client.head_profile.return_value = (200, "remote-sha")

    with patch("app.browser.profile_sync.resolve_profile_dir", return_value=tmp_path):
        with patch("app.browser.profile_sync.should_pull_remote", return_value=False):
            pulled = pull_profile_if_needed(
                client,
                platform="temu",
                tenant_id=5,
                session_key="18061740604",
            )
    assert pulled is False
    client.download_profile.assert_not_called()


def test_pull_profile_unpacks_on_200(tmp_path) -> None:
    client = MagicMock()
    client.resolve_agent_tenant_id.return_value = 5
    client.head_profile.return_value = (200, "remote-sha")
    client.download_profile.return_value = (b"PK\x03\x04", "remote-sha")

    with patch("app.browser.profile_sync.resolve_profile_dir", return_value=tmp_path):
        with patch("app.browser.profile_sync.should_pull_remote", return_value=True):
            with patch("app.browser.profile_sync.unpack_profile_bundle") as unpack:
                with patch("app.browser.profile_sync.write_remote_sha_cache") as write_cache:
                    pulled = pull_profile_if_needed(
                        client,
                        platform="temu",
                        tenant_id=5,
                        session_key="18061740604",
                    )
    assert pulled is True
    unpack.assert_called_once()
    write_cache.assert_called_once()


def test_pull_profile_404_no_error(tmp_path) -> None:
    client = MagicMock()
    client.resolve_agent_tenant_id.return_value = 5
    client.head_profile.return_value = (404, "")

    with patch("app.browser.profile_sync.resolve_profile_dir", return_value=tmp_path):
        assert pull_profile_if_needed(
            client,
            platform="temu",
            tenant_id=5,
            session_key="18061740604",
        ) is False
