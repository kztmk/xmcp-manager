from __future__ import annotations

from typing import Any

CURRENT_APP_SETTINGS_VERSION = 1
CURRENT_ACCOUNTS_VERSION = 1
CURRENT_CREDENTIALS_VERSION = 1
CURRENT_TOOL_CATALOG_VERSION = 1


def ensure_supported_version(data: dict[str, Any], current: int, label: str) -> None:
    version = data.get("version", 1)
    if not isinstance(version, int):
        raise ValueError(f"{label} version must be an integer.")
    if version > current:
        raise ValueError(f"{label} version {version} is newer than supported {current}.")


def migrate_app_settings(data: dict[str, Any]) -> dict[str, Any]:
    ensure_supported_version(data, CURRENT_APP_SETTINGS_VERSION, "App Settings")
    return data


def migrate_accounts(data: dict[str, Any]) -> dict[str, Any]:
    ensure_supported_version(data, CURRENT_ACCOUNTS_VERSION, "Account Metadata")
    return data


def migrate_credentials(data: dict[str, Any]) -> dict[str, Any]:
    ensure_supported_version(data, CURRENT_CREDENTIALS_VERSION, "API Credentials")
    return data


def migrate_tool_catalog(data: dict[str, Any]) -> dict[str, Any]:
    ensure_supported_version(data, CURRENT_TOOL_CATALOG_VERSION, "Tool Catalog")
    return data
