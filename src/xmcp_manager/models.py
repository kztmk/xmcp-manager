from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class CredentialStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    INVALID = "invalid"
    INACCESSIBLE = "inaccessible"


class ToolPreset(StrEnum):
    READ_ONLY = "read_only"
    BROAD_WRITE = "broad_write"
    FULL_ACCESS = "full_access"
    CUSTOM = "custom"


class RiskLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    SENSITIVE = "sensitive"
    UNKNOWN = "unknown"


class ServerState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    WAITING_AUTH = "waiting_auth"
    CONNECTABLE = "connectable"
    ERROR = "error"


class McpClientId(StrEnum):
    CLAUDE_DESKTOP = "claude-desktop"
    CODEX_DESKTOP = "codex-desktop"


@dataclass
class StoreValidation:
    version: int = 1
    app_version: str | None = None
    external_config_writable: dict[str, bool | None] = field(
        default_factory=lambda: {
            McpClientId.CLAUDE_DESKTOP.value: None,
            McpClientId.CODEX_DESKTOP.value: None,
        }
    )
    loopback_available: bool | None = None
    credential_store_available: bool | None = None
    user_data_writable: bool | None = None
    validated_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppSettings:
    version: int = 1
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    oauth_callback_host: str = "127.0.0.1"
    oauth_callback_port: int = 8976
    oauth_callback_path: str = "/oauth/callback"
    selected_mcp_clients: list[str] = field(default_factory=list)
    client_overwrite_accepted_urls: dict[str, str | None] = field(
        default_factory=lambda: {
            McpClientId.CLAUDE_DESKTOP.value: None,
            McpClientId.CODEX_DESKTOP.value: None,
        }
    )
    store_validation: StoreValidation = field(default_factory=StoreValidation)
    broad_write_preset_warning_accepted: bool = False
    full_access_warning_accepted: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def endpoint_url(self) -> str:
        return f"http://{self.mcp_host}:{self.mcp_port}/mcp"

    @property
    def callback_uri(self) -> str:
        return (
            f"http://{self.oauth_callback_host}:"
            f"{self.oauth_callback_port}{self.oauth_callback_path}"
        )


@dataclass
class Account:
    id: str
    handle: str
    display_name: str = ""
    last_used_at: str | None = None
    tool_allowlist_preset: ToolPreset = ToolPreset.BROAD_WRITE
    tool_allowlist: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    credential_status: CredentialStatus = CredentialStatus.MISSING
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.display_name} ({self.handle})" if self.display_name else self.handle


@dataclass
class AccountMetadataDocument:
    version: int = 1
    accounts: list[Account] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApiCredentials:
    version: int = 1
    consumer_key: str = ""
    consumer_secret: str = ""
    bearer_token: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    name: str
    category: str
    action_type: str
    risk_level: RiskLevel
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCatalog:
    version: int
    source: str
    generated_at: str
    xmcp_revision: str
    tools: list[ToolDefinition]
    extra: dict[str, Any] = field(default_factory=dict)

    def by_name(self) -> dict[str, ToolDefinition]:
        return {tool.name: tool for tool in self.tools}


@dataclass
class ValidationResult:
    ok: bool
    invalid_tools: list[str] = field(default_factory=list)
    unknown_tools: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class AllowlistResult:
    env_value: str | None
    tools: list[str]
    validation: ValidationResult


@dataclass
class WarningSet:
    broad_write: bool = False
    full_access: bool = False
    unknown_custom_tools: list[str] = field(default_factory=list)


@dataclass
class RefreshResult:
    ok: bool
    catalog: ToolCatalog | None = None
    message: str = ""


@dataclass
class ClientConfigStatus:
    client_id: str
    config_path: str
    exists: bool
    current_url: str | None = None
    matches: bool = False
    parse_error: str | None = None


@dataclass
class BackupInfo:
    client_id: str
    source_path: str
    backup_path: str
    created_at: str


@dataclass
class ClientUpdateResult:
    client_id: str
    ok: bool
    message: str
    backup: BackupInfo | None = None
    manual_snippet: str | None = None


@dataclass
class UpdateResult:
    ok: bool
    results: list[ClientUpdateResult]


@dataclass
class DeleteResult:
    ok: bool
    message: str = ""


@dataclass
class StartResult:
    ok: bool
    message: str = ""


@dataclass
class StopResult:
    ok: bool
    message: str = ""


@dataclass
class UnmanagedServerStatus:
    detected: bool
    endpoint_url: str
    message: str = ""


@dataclass
class ServerStateSnapshot:
    state: ServerState = ServerState.STOPPED
    account_id: str | None = None
    account_label: str | None = None
    message: str = ""
    logs: list[str] = field(default_factory=list)


StateListener = Callable[[ServerStateSnapshot], None]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
