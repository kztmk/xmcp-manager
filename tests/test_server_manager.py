from __future__ import annotations

import time

from xmcp_manager.models import Account, ApiCredentials, AppSettings, ServerState
from xmcp_manager.server_manager import ServerManager


class FakeProcess:
    stdout = []
    returncode: int | None = None
    terminated = False
    killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode or 0


def test_start_reaches_connectable_and_stop(monkeypatch, tmp_path) -> None:
    server_dir = tmp_path / "xmcp"
    server_dir.mkdir()
    (server_dir / "server.py").write_text("print('fake')\n", encoding="utf-8")
    monkeypatch.setattr("xmcp_manager.paths.get_vendored_xmcp_dir", lambda: server_dir)
    monkeypatch.setattr(ServerManager, "detect_unmanaged", lambda self, endpoint: type(
        "Status",
        (),
        {"detected": False, "message": "", "endpoint_url": endpoint},
    )())
    monkeypatch.setattr(ServerManager, "_probe_connectable", lambda self, endpoint: True)
    fake_process = FakeProcess()
    captured_env: dict[str, str] = {}

    def fake_popen(*args, **kwargs) -> FakeProcess:
        captured_env.update(kwargs["env"])
        return fake_process

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    manager = ServerManager()
    manager._startup_timeout_sec = 10
    result = manager.start(
        Account(id="account-id", handle="@example"),
        ApiCredentials(consumer_key="key", consumer_secret="secret", bearer_token="bearer"),
        "getUsersMe",
        AppSettings(mcp_port=8765),
    )

    assert result.ok
    deadline = time.time() + 10
    while time.time() < deadline:
        if manager.get_state().state is ServerState.CONNECTABLE:
            break
        time.sleep(0.1)

    assert manager.get_state().state is ServerState.CONNECTABLE
    assert captured_env["X_OAUTH_CONSUMER_KEY"] == "key"
    assert captured_env["X_API_TOOL_ALLOWLIST"] == "getUsersMe"
    assert captured_env["MCP_PORT"] == "8765"
    stop = manager.stop()
    assert stop.ok
    assert fake_process.terminated
    assert manager.get_state().state is ServerState.STOPPED
