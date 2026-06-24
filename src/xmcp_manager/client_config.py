from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import tomlkit

from xmcp_manager import paths
from xmcp_manager.models import (
    BackupInfo,
    ClientConfigStatus,
    ClientUpdateResult,
    McpClientId,
    UpdateResult,
    utc_now_iso,
)


class ClientConfigError(RuntimeError):
    pass


def _timestamp_for_filename() -> str:
    return utc_now_iso().replace(":", "").replace("-", "").replace("Z", "Z")


def get_claude_config_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"


def get_codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def _config_path_for(client_id: str) -> Path:
    if client_id == McpClientId.CLAUDE_DESKTOP.value:
        return get_claude_config_path()
    if client_id == McpClientId.CODEX_DESKTOP.value:
        return get_codex_config_path()
    raise ClientConfigError(f"Unknown MCP client: {client_id}")


def claude_snippet(endpoint_url: str) -> str:
    return json.dumps({"mcpServers": {"xmcp": {"url": endpoint_url}}}, indent=2)


def codex_snippet(endpoint_url: str) -> str:
    doc = tomlkit.document()
    servers = tomlkit.table()
    xmcp = tomlkit.table()
    xmcp.add("url", endpoint_url)
    xmcp.add("enabled", True)
    servers.add("xmcp", xmcp)
    doc.add("mcp_servers", servers)
    return tomlkit.dumps(doc).strip()


def manual_snippet(client_id: str, endpoint_url: str) -> str:
    if client_id == McpClientId.CLAUDE_DESKTOP.value:
        return claude_snippet(endpoint_url)
    if client_id == McpClientId.CODEX_DESKTOP.value:
        return codex_snippet(endpoint_url)
    raise ClientConfigError(f"Unknown MCP client: {client_id}")


def create_backup(client_id: str, config_path: Path) -> BackupInfo:
    created_at = utc_now_iso()
    backup_dir = paths.get_backup_dir(client_id)
    backup_dir.mkdir(parents=True, exist_ok=True)
    suffix = config_path.suffix or ".config"
    backup_path = backup_dir / f"{config_path.name}.{_timestamp_for_filename()}{suffix}.bak"
    shutil.copy2(config_path, backup_path)
    return BackupInfo(
        client_id=client_id,
        source_path=str(config_path),
        backup_path=str(backup_path),
        created_at=created_at,
    )


def prune_backups(client_id: str, keep: int = 10) -> None:
    backup_dir = paths.get_backup_dir(client_id)
    backups = sorted(
        [path for path in backup_dir.iterdir() if path.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for backup in backups[keep:]:
        backup.unlink(missing_ok=True)


def _load_claude_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ClientConfigError("Claude config must be a JSON object.")
    return data


def _load_codex_config(path: Path) -> Any:
    if not path.exists():
        return tomlkit.document()
    with path.open("r", encoding="utf-8") as f:
        return tomlkit.parse(f.read())


def get_client_config_status(client_id: str, endpoint_url: str) -> ClientConfigStatus:
    path = _config_path_for(client_id)
    if not path.exists():
        return ClientConfigStatus(
            client_id=client_id,
            config_path=str(path),
            exists=False,
            current_url=None,
            matches=False,
        )
    try:
        if client_id == McpClientId.CLAUDE_DESKTOP.value:
            data = _load_claude_config(path)
            current_url = data.get("mcpServers", {}).get("xmcp", {}).get("url")
        else:
            data = _load_codex_config(path)
            current_url = data.get("mcp_servers", {}).get("xmcp", {}).get("url")
        current_url = str(current_url) if current_url else None
        return ClientConfigStatus(
            client_id=client_id,
            config_path=str(path),
            exists=True,
            current_url=current_url,
            matches=current_url == endpoint_url,
        )
    except Exception as exc:  # noqa: BLE001 - status should carry parse errors
        return ClientConfigStatus(
            client_id=client_id,
            config_path=str(path),
            exists=True,
            parse_error=str(exc),
        )


def update_claude_config(endpoint_url: str) -> ClientUpdateResult:
    client_id = McpClientId.CLAUDE_DESKTOP.value
    path = get_claude_config_path()
    try:
        data = _load_claude_config(path)
        backup = create_backup(client_id, path) if path.exists() else None
        data.setdefault("mcpServers", {})["xmcp"] = {"url": endpoint_url}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        prune_backups(client_id)
        return ClientUpdateResult(
            client_id=client_id,
            ok=True,
            message="Claude config updated.",
            backup=backup,
        )
    except Exception as exc:  # noqa: BLE001 - convert to user-facing result
        return ClientUpdateResult(
            client_id=client_id,
            ok=False,
            message=str(exc),
            manual_snippet=manual_snippet(client_id, endpoint_url),
        )


def update_codex_config(endpoint_url: str) -> ClientUpdateResult:
    client_id = McpClientId.CODEX_DESKTOP.value
    path = get_codex_config_path()
    try:
        doc = _load_codex_config(path)
        backup = create_backup(client_id, path) if path.exists() else None
        servers = doc.get("mcp_servers")
        if servers is None:
            servers = tomlkit.table()
            doc["mcp_servers"] = servers
        if "xmcp" not in servers:
            servers["xmcp"] = tomlkit.table()
        servers["xmcp"]["url"] = endpoint_url
        servers["xmcp"]["enabled"] = True
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        prune_backups(client_id)
        return ClientUpdateResult(
            client_id=client_id,
            ok=True,
            message="Codex config updated.",
            backup=backup,
        )
    except Exception as exc:  # noqa: BLE001
        return ClientUpdateResult(
            client_id=client_id,
            ok=False,
            message=str(exc),
            manual_snippet=manual_snippet(client_id, endpoint_url),
        )


def update_selected_clients(client_ids: list[str], endpoint_url: str) -> UpdateResult:
    if not client_ids:
        return UpdateResult(ok=False, results=[])
    results: list[ClientUpdateResult] = []
    for client_id in client_ids:
        if client_id == McpClientId.CLAUDE_DESKTOP.value:
            results.append(update_claude_config(endpoint_url))
        elif client_id == McpClientId.CODEX_DESKTOP.value:
            results.append(update_codex_config(endpoint_url))
        else:
            results.append(
                ClientUpdateResult(
                    client_id=client_id,
                    ok=False,
                    message=f"Unknown MCP client: {client_id}",
                )
            )
    return UpdateResult(ok=all(result.ok for result in results), results=results)
