from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from xmcp_manager import paths
from xmcp_manager.migrations import migrate_accounts, migrate_credentials
from xmcp_manager.models import (
    Account,
    AccountMetadataDocument,
    ApiCredentials,
    CredentialStatus,
    DeleteResult,
    ToolPreset,
    utc_now_iso,
)

SERVICE_NAME = "XMCP Manager"
SaveMode = Literal["create", "update"]


class StoreError(RuntimeError):
    pass


def _known_extra(data: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key not in known}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise StoreError(f"{path} must contain a JSON object.")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _account_from_dict(data: dict[str, Any]) -> Account:
    known = {
        "id",
        "handle",
        "displayName",
        "lastUsedAt",
        "toolAllowlistPreset",
        "toolAllowlist",
        "settings",
    }
    return Account(
        id=str(data["id"]),
        handle=str(data["handle"]),
        display_name=str(data.get("displayName") or ""),
        last_used_at=data.get("lastUsedAt"),
        tool_allowlist_preset=ToolPreset(data.get("toolAllowlistPreset", ToolPreset.BROAD_WRITE)),
        tool_allowlist=[str(item) for item in data.get("toolAllowlist", [])],
        settings=dict(data.get("settings", {})),
        extra=_known_extra(data, known),
    )


def _account_to_dict(account: Account) -> dict[str, Any]:
    data = dict(account.extra)
    data.update(
        {
            "id": account.id,
            "handle": account.handle,
            "displayName": account.display_name,
            "lastUsedAt": account.last_used_at,
            "toolAllowlistPreset": account.tool_allowlist_preset.value,
            "toolAllowlist": account.tool_allowlist,
            "settings": account.settings,
        }
    )
    return data


def load_accounts() -> AccountMetadataDocument:
    path = paths.get_accounts_path()
    if not path.exists():
        return AccountMetadataDocument()
    raw = migrate_accounts(_read_json(path))
    known = {"version", "accounts"}
    accounts_raw = raw.get("accounts", [])
    if not isinstance(accounts_raw, list):
        raise StoreError("Account Metadata accounts must be a list.")
    doc = AccountMetadataDocument(
        version=int(raw.get("version", 1)),
        accounts=[_account_from_dict(item) for item in accounts_raw if isinstance(item, dict)],
        extra=_known_extra(raw, known),
    )
    for account in doc.accounts:
        account.credential_status = get_credentials_status(account.id)
    return doc


def save_accounts(doc: AccountMetadataDocument) -> None:
    data = dict(doc.extra)
    data.update(
        {
            "version": doc.version,
            "accounts": [_account_to_dict(account) for account in doc.accounts],
        }
    )
    _write_json(paths.get_accounts_path(), data)


def create_account(handle: str, display_name: str) -> Account:
    clean_handle = handle.strip()
    if not clean_handle:
        raise StoreError("Account handle is required.")
    if not clean_handle.startswith("@"):
        clean_handle = f"@{clean_handle}"
    return Account(
        id=str(uuid.uuid4()),
        handle=clean_handle,
        display_name=display_name.strip(),
        last_used_at=utc_now_iso(),
    )


def delete_account(account_id: str) -> DeleteResult:
    doc = load_accounts()
    before = len(doc.accounts)
    doc.accounts = [account for account in doc.accounts if account.id != account_id]
    if len(doc.accounts) == before:
        return DeleteResult(ok=False, message="Account not found.")
    credential_warning = ""
    try:
        delete_credentials(account_id)
    except StoreError as exc:
        credential_warning = f" Credentials delete failed: {exc}"
    save_accounts(doc)
    return DeleteResult(ok=not credential_warning, message=credential_warning.strip())


def _credentials_from_dict(data: dict[str, Any]) -> ApiCredentials:
    known = {"version", "consumerKey", "consumerSecret", "bearerToken"}
    data = migrate_credentials(data)
    return ApiCredentials(
        version=int(data.get("version", 1)),
        consumer_key=str(data.get("consumerKey") or ""),
        consumer_secret=str(data.get("consumerSecret") or ""),
        bearer_token=str(data.get("bearerToken") or ""),
        extra=_known_extra(data, known),
    )


def _credentials_to_dict(credentials: ApiCredentials) -> dict[str, Any]:
    data = dict(credentials.extra)
    data.update(
        {
            "version": credentials.version,
            "consumerKey": credentials.consumer_key,
            "consumerSecret": credentials.consumer_secret,
            "bearerToken": credentials.bearer_token,
        }
    )
    return data


def _validate_value(name: str, value: str) -> str:
    clean = value.strip()
    if not clean:
        raise StoreError(f"{name} is required.")
    if "\n" in clean or "\r" in clean:
        raise StoreError(f"{name} must not contain line breaks.")
    return clean


def _validate_credentials(credentials: ApiCredentials) -> ApiCredentials:
    credentials.consumer_key = _validate_value("API Key", credentials.consumer_key)
    credentials.consumer_secret = _validate_value("API Key Secret", credentials.consumer_secret)
    credentials.bearer_token = _validate_value("Bearer Token", credentials.bearer_token)
    return credentials


def _get_raw_credentials(account_id: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, account_id)


def get_credentials_status(account_id: str) -> CredentialStatus:
    try:
        raw = _get_raw_credentials(account_id)
    except KeyringError:
        return CredentialStatus.INACCESSIBLE
    if raw is None:
        return CredentialStatus.MISSING
    try:
        credentials = _credentials_from_dict(json.loads(raw))
        _validate_credentials(credentials)
    except (json.JSONDecodeError, StoreError, TypeError, ValueError):
        return CredentialStatus.INVALID
    return CredentialStatus.OK


def save_credentials(
    account_id: str,
    partial_credentials: dict[str, str],
    mode: SaveMode = "update",
) -> None:
    existing = ApiCredentials()
    if mode == "update":
        try:
            existing = load_credentials_for_start(account_id)
        except StoreError:
            existing = ApiCredentials()
    credentials = ApiCredentials(
        consumer_key=partial_credentials.get("consumerKey", "").strip()
        or partial_credentials.get("consumer_key", "").strip()
        or existing.consumer_key,
        consumer_secret=partial_credentials.get("consumerSecret", "").strip()
        or partial_credentials.get("consumer_secret", "").strip()
        or existing.consumer_secret,
        bearer_token=partial_credentials.get("bearerToken", "").strip()
        or partial_credentials.get("bearer_token", "").strip()
        or existing.bearer_token,
        extra=existing.extra,
    )
    _validate_credentials(credentials)
    try:
        keyring.set_password(
            SERVICE_NAME,
            account_id,
            json.dumps(_credentials_to_dict(credentials)),
        )
    except KeyringError as exc:
        raise StoreError(f"Could not save credentials to keychain: {exc}") from exc


def load_credentials_for_start(account_id: str) -> ApiCredentials:
    try:
        raw = _get_raw_credentials(account_id)
    except KeyringError as exc:
        raise StoreError(f"Could not access credentials: {exc}") from exc
    if raw is None:
        raise StoreError("Credentials are missing.")
    try:
        credentials = _credentials_from_dict(json.loads(raw))
        return _validate_credentials(credentials)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise StoreError("Credentials are invalid.") from exc


def delete_credentials(account_id: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, account_id)
    except PasswordDeleteError:
        return
    except KeyringError as exc:
        raise StoreError(f"Could not delete credentials: {exc}") from exc
