from agent.protocol_launch import is_protocol_start_argv, ports_already_serving

def test_is_protocol_start_flag():
    assert is_protocol_start_argv(["sync_helper_app.py", "--protocol-start"]) is True
    assert is_protocol_start_argv(["CrossHub-Sync-Helper.exe", "crosshub-sync-helper://start"]) is True
    assert is_protocol_start_argv(["CrossHub-Sync-Helper.exe", "crosshub-sync-helper://start/"]) is True
    assert is_protocol_start_argv(["CrossHub-Sync-Helper.exe"]) is False
    assert is_protocol_start_argv(["app", "crosshub-sync-helper://other"]) is False

def test_ports_already_serving_false_when_closed(monkeypatch):
    class Boom:
        def __enter__(self):
            raise OSError("closed")
        def __exit__(self, *a):
            return False

    import agent.protocol_launch as pl
    monkeypatch.setattr(pl.socket, "create_connection", lambda *a, **k: Boom())
    assert ports_already_serving(18765, 18766) is False
