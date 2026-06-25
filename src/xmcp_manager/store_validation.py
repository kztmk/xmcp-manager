from __future__ import annotations

import os
import socket
import uuid
from pathlib import Path

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from xmcp_manager import __version__, paths
from xmcp_manager.account_store import SERVICE_NAME
from xmcp_manager.client_config import get_claude_config_path, get_codex_config_path
from xmcp_manager.models import AppSettings, McpClientId, StoreValidation, utc_now_iso


def is_store_build() -> bool:
    return os.environ.get("XMCP_STORE_BUILD", "").strip().lower() in {"1", "true", "yes", "on"}


def validation_is_current(settings: AppSettings) -> bool:
    return settings.store_validation.app_version == __version__


def _can_write_marker(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        marker = directory / f".xmcp-manager-validation-{uuid.uuid4().hex}.tmp"
        marker.write_text("ok", encoding="utf-8")
        marker.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def check_user_data_writable() -> bool:
    return _can_write_marker(paths.get_user_data_dir())


def check_external_config_writable(client_id: str) -> bool:
    if client_id == McpClientId.CLAUDE_DESKTOP.value:
        config_path = get_claude_config_path()
    elif client_id == McpClientId.CODEX_DESKTOP.value:
        config_path = get_codex_config_path()
    else:
        return False
    return _can_write_marker(config_path.parent)


def check_loopback_available(host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            sock.listen(1)
        return True
    except OSError:
        return False


def check_credential_store_available() -> bool:
    account = f"__xmcp_manager_validation__:{uuid.uuid4().hex}"
    try:
        keyring.set_password(SERVICE_NAME, account, "ok")
        ok = keyring.get_password(SERVICE_NAME, account) == "ok"
        try:
            keyring.delete_password(SERVICE_NAME, account)
        except PasswordDeleteError:
            pass
        return ok
    except KeyringError:
        return False


def run_store_validation(settings: AppSettings) -> StoreValidation:
    return StoreValidation(
        version=1,
        app_version=__version__,
        external_config_writable={
            McpClientId.CLAUDE_DESKTOP.value: check_external_config_writable(
                McpClientId.CLAUDE_DESKTOP.value
            ),
            McpClientId.CODEX_DESKTOP.value: check_external_config_writable(
                McpClientId.CODEX_DESKTOP.value
            ),
        },
        loopback_available=check_loopback_available(settings.mcp_host),
        credential_store_available=check_credential_store_available(),
        user_data_writable=check_user_data_writable(),
        validated_at=utc_now_iso(),
    )


def format_store_validation(validation: StoreValidation) -> str:
    external = validation.external_config_writable
    return "\n".join(
        [
            f"app version: {validation.app_version or '-'}",
            f"validated at: {validation.validated_at or '-'}",
            f"user data writable: {validation.user_data_writable}",
            f"credential store available: {validation.credential_store_available}",
            f"loopback available: {validation.loopback_available}",
            (
                "Claude Desktop config writable: "
                f"{external.get(McpClientId.CLAUDE_DESKTOP.value)}"
            ),
            (
                "Codex Desktop config writable: "
                f"{external.get(McpClientId.CODEX_DESKTOP.value)}"
            ),
        ]
    )
