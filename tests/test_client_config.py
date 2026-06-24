import json

from xmcp_manager.client_config import (
    codex_snippet,
    get_client_config_status,
    update_claude_config,
)
from xmcp_manager.models import McpClientId


def test_codex_snippet_contains_streamable_http_url() -> None:
    snippet = codex_snippet("http://127.0.0.1:8000/mcp")

    assert "[mcp_servers.xmcp]" in snippet
    assert 'url = "http://127.0.0.1:8000/mcp"' in snippet
    assert "enabled = true" in snippet


def test_update_claude_config_preserves_other_servers(monkeypatch, tmp_path) -> None:
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(
        json.dumps({"mcpServers": {"other": {"url": "http://example.test/mcp"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("xmcp_manager.client_config.get_claude_config_path", lambda: config)
    monkeypatch.setattr("xmcp_manager.paths.get_backup_dir", lambda client_id: tmp_path / "backups")

    result = update_claude_config("http://127.0.0.1:8000/mcp")
    status = get_client_config_status(
        McpClientId.CLAUDE_DESKTOP.value, "http://127.0.0.1:8000/mcp"
    )

    updated = json.loads(config.read_text(encoding="utf-8"))
    assert result.ok is True
    assert updated["mcpServers"]["other"]["url"] == "http://example.test/mcp"
    assert updated["mcpServers"]["xmcp"]["url"] == "http://127.0.0.1:8000/mcp"
    assert status.matches is True
