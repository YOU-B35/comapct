from agent.install_marker import marker_path, read_install_marker, write_install_marker


def test_write_and_read_install_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    write_install_marker(version="test")
    data = read_install_marker()
    assert data is not None
    assert data["installed"] is True
    assert data["version"] == "test"
    assert marker_path() == tmp_path / "CrossHub" / "SyncHelper" / "installed.json"
    assert marker_path().is_file()
