from __future__ import annotations

import json
from typing import Any

from xmcp_manager import __version__, paths
from xmcp_manager.migrations import migrate_app_settings
from xmcp_manager.models import AppSettings, StoreValidation


class AppSettingsError(RuntimeError):
    pass


def _extra(data: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key not in known}


def _store_validation_from_dict(data: dict[str, Any]) -> StoreValidation:
    known = {
        "version",
        "appVersion",
        "externalConfigWritable",
        "loopbackAvailable",
        "credentialStoreAvailable",
        "userDataWritable",
        "validatedAt",
    }
    external = data.get("externalConfigWritable") or {}
    return StoreValidation(
        version=int(data.get("version", 1)),
        app_version=data.get("appVersion"),
        external_config_writable=dict(external),
        loopback_available=data.get("loopbackAvailable"),
        credential_store_available=data.get("credentialStoreAvailable"),
        user_data_writable=data.get("userDataWritable"),
        validated_at=data.get("validatedAt"),
        extra=_extra(data, known),
    )


def _store_validation_to_dict(store_validation: StoreValidation) -> dict[str, Any]:
    data = dict(store_validation.extra)
    data.update(
        {
            "version": store_validation.version,
            "appVersion": store_validation.app_version,
            "externalConfigWritable": store_validation.external_config_writable,
            "loopbackAvailable": store_validation.loopback_available,
            "credentialStoreAvailable": store_validation.credential_store_available,
            "userDataWritable": store_validation.user_data_writable,
            "validatedAt": store_validation.validated_at,
        }
    )
    return data


def load_app_settings() -> AppSettings:
    path = paths.get_app_settings_path()
    if not path.exists():
        return AppSettings()
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise AppSettingsError("App Settings must be a JSON object.")
        raw = migrate_app_settings(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise AppSettingsError(str(exc)) from exc
    known = {
        "version",
        "mcpHost",
        "mcpPort",
        "oauthCallbackHost",
        "oauthCallbackPort",
        "oauthCallbackPath",
        "selectedMcpClients",
        "clientOverwriteAcceptedUrls",
        "storeValidation",
        "broadWritePresetWarningAccepted",
        "fullAccessWarningAccepted",
    }
    return AppSettings(
        version=int(raw.get("version", 1)),
        mcp_host=str(raw.get("mcpHost") or "127.0.0.1"),
        mcp_port=int(raw.get("mcpPort") or 8000),
        oauth_callback_host=str(raw.get("oauthCallbackHost") or "127.0.0.1"),
        oauth_callback_port=int(raw.get("oauthCallbackPort") or 8976),
        oauth_callback_path=str(raw.get("oauthCallbackPath") or "/oauth/callback"),
        selected_mcp_clients=[str(item) for item in raw.get("selectedMcpClients", [])],
        client_overwrite_accepted_urls=dict(raw.get("clientOverwriteAcceptedUrls") or {}),
        store_validation=_store_validation_from_dict(raw.get("storeValidation") or {}),
        broad_write_preset_warning_accepted=bool(
            raw.get("broadWritePresetWarningAccepted", False)
        ),
        full_access_warning_accepted=bool(raw.get("fullAccessWarningAccepted", False)),
        extra=_extra(raw, known),
    )


def save_app_settings(settings: AppSettings) -> None:
    data = dict(settings.extra)
    data.update(
        {
            "version": settings.version,
            "mcpHost": settings.mcp_host,
            "mcpPort": settings.mcp_port,
            "oauthCallbackHost": settings.oauth_callback_host,
            "oauthCallbackPort": settings.oauth_callback_port,
            "oauthCallbackPath": settings.oauth_callback_path,
            "selectedMcpClients": settings.selected_mcp_clients,
            "clientOverwriteAcceptedUrls": settings.client_overwrite_accepted_urls,
            "storeValidation": _store_validation_to_dict(settings.store_validation),
            "broadWritePresetWarningAccepted": settings.broad_write_preset_warning_accepted,
            "fullAccessWarningAccepted": settings.full_access_warning_accepted,
        }
    )
    path = paths.get_app_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def mark_store_validation_current(settings: AppSettings) -> AppSettings:
    settings.store_validation.app_version = __version__
    return settings
