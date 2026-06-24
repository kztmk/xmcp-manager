from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from xmcp_manager import paths
from xmcp_manager.migrations import migrate_tool_catalog
from xmcp_manager.models import (
    AllowlistResult,
    RefreshResult,
    RiskLevel,
    ToolCatalog,
    ToolDefinition,
    ToolPreset,
    ValidationResult,
    WarningSet,
)

OPENAPI_URL = "https://api.x.com/2/openapi.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


class CatalogError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise CatalogError(f"{path} must contain a JSON object.")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _tool_from_dict(data: dict[str, Any]) -> ToolDefinition:
    known = {"name", "category", "actionType", "riskLevel", "description"}
    return ToolDefinition(
        name=str(data["name"]),
        category=str(data.get("category") or "Other"),
        action_type=str(data.get("actionType") or "other"),
        risk_level=RiskLevel(data.get("riskLevel", RiskLevel.UNKNOWN)),
        description=str(data.get("description") or ""),
        extra={key: value for key, value in data.items() if key not in known},
    )


def _tool_to_dict(tool: ToolDefinition) -> dict[str, Any]:
    data = dict(tool.extra)
    data.update(
        {
            "name": tool.name,
            "category": tool.category,
            "actionType": tool.action_type,
            "riskLevel": tool.risk_level.value,
            "description": tool.description,
        }
    )
    return data


def _catalog_from_dict(data: dict[str, Any]) -> ToolCatalog:
    data = migrate_tool_catalog(data)
    known = {"version", "source", "generatedAt", "xmcpRevision", "tools"}
    tools_raw = data.get("tools", [])
    if not isinstance(tools_raw, list):
        raise CatalogError("Tool Catalog tools must be a list.")
    return ToolCatalog(
        version=int(data.get("version", 1)),
        source=str(data.get("source") or "unknown"),
        generated_at=str(data.get("generatedAt") or ""),
        xmcp_revision=str(data.get("xmcpRevision") or ""),
        tools=[_tool_from_dict(item) for item in tools_raw if isinstance(item, dict)],
        extra={key: value for key, value in data.items() if key not in known},
    )


def _catalog_to_dict(catalog: ToolCatalog) -> dict[str, Any]:
    data = dict(catalog.extra)
    data.update(
        {
            "version": catalog.version,
            "source": catalog.source,
            "generatedAt": catalog.generated_at,
            "xmcpRevision": catalog.xmcp_revision,
            "tools": [_tool_to_dict(tool) for tool in catalog.tools],
        }
    )
    return data


def load_tool_catalog() -> ToolCatalog:
    user_path = paths.get_user_tool_catalog_path()
    if user_path.exists():
        try:
            return _catalog_from_dict(_read_json(user_path))
        except (OSError, json.JSONDecodeError, CatalogError, ValueError):
            pass
    bundled = paths.get_bundled_resource_path("tool_catalog.json")
    return _catalog_from_dict(_read_json(bundled))


def _infer_tool(operation_id: str, operation: dict[str, Any]) -> ToolDefinition:
    lower = operation_id.lower()
    tags = operation.get("tags") or []
    tag = str(tags[0]) if tags else "Other"
    category = tag[:1].upper() + tag[1:] if tag else "Other"
    action_type = "other"
    risk = RiskLevel.UNKNOWN
    if any(term in lower for term in ("dm", "directmessage", "direct_message")):
        action_type = "dm"
        risk = RiskLevel.SENSITIVE
    elif "delete" in lower or "block" in lower:
        action_type = "block" if "block" in lower else "post"
        risk = RiskLevel.DESTRUCTIVE
    elif any(term in lower for term in ("create", "update", "post", "follow", "like", "repost")):
        if "follow" in lower:
            action_type = "follow"
        elif "media" in lower:
            action_type = "media"
        else:
            action_type = "post"
        risk = RiskLevel.WRITE
    elif any(term in lower for term in ("get", "list", "search", "lookup")):
        if "search" in lower:
            action_type = "search"
        elif "user" in lower or "profile" in lower:
            action_type = "profile"
        elif "list" in lower:
            action_type = "list"
        else:
            action_type = "other"
        risk = RiskLevel.READ
    return ToolDefinition(
        name=operation_id,
        category=category,
        action_type=action_type,
        risk_level=risk,
        description=str(operation.get("summary") or operation.get("description") or ""),
    )


def catalog_from_openapi_spec(spec: dict[str, Any], xmcp_revision: str = "") -> ToolCatalog:
    tools: list[ToolDefinition] = []
    for item in spec.get("paths", {}).values():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str) and operation_id:
                tools.append(_infer_tool(operation_id, operation))
    tools.sort(key=lambda tool: tool.name)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return ToolCatalog(
        version=1,
        source="refresh",
        generated_at=generated_at,
        xmcp_revision=xmcp_revision,
        tools=tools,
    )


def refresh_tool_catalog() -> RefreshResult:
    try:
        response = httpx.get(OPENAPI_URL, timeout=30)
        response.raise_for_status()
        catalog = catalog_from_openapi_spec(response.json())
        _write_json(paths.get_user_tool_catalog_path(), _catalog_to_dict(catalog))
        return RefreshResult(ok=True, catalog=catalog, message="Tool Catalog refreshed.")
    except Exception as exc:  # noqa: BLE001 - user-facing refresh should preserve old catalog
        return RefreshResult(ok=False, catalog=None, message=str(exc))


def validate_custom_tools(custom_tools: list[str], catalog: ToolCatalog) -> ValidationResult:
    by_name = catalog.by_name()
    invalid = [tool for tool in custom_tools if tool not in by_name]
    unknown = [
        tool
        for tool in custom_tools
        if tool in by_name and by_name[tool].risk_level is RiskLevel.UNKNOWN
    ]
    return ValidationResult(ok=not invalid, invalid_tools=invalid, unknown_tools=unknown)


def generate_allowlist(
    preset: ToolPreset | str,
    custom_tools: list[str],
    catalog: ToolCatalog,
) -> AllowlistResult:
    preset = ToolPreset(preset)
    if preset is ToolPreset.FULL_ACCESS:
        return AllowlistResult(env_value=None, tools=[], validation=ValidationResult(ok=True))
    if preset is ToolPreset.CUSTOM:
        validation = validate_custom_tools(custom_tools, catalog)
        tools = list(dict.fromkeys(custom_tools))
        return AllowlistResult(
            env_value=",".join(tools) if tools else "",
            tools=tools,
            validation=validation,
        )
    if preset is ToolPreset.READ_ONLY:
        allowed_risks = {RiskLevel.READ}
    else:
        allowed_risks = {
            RiskLevel.READ,
            RiskLevel.WRITE,
            RiskLevel.DESTRUCTIVE,
            RiskLevel.SENSITIVE,
        }
    tools = [tool.name for tool in catalog.tools if tool.risk_level in allowed_risks]
    return AllowlistResult(
        env_value=",".join(tools),
        tools=tools,
        validation=ValidationResult(ok=True),
    )


def requires_warning(
    preset: ToolPreset | str,
    allowlist: list[str],
    catalog: ToolCatalog,
) -> WarningSet:
    preset = ToolPreset(preset)
    warnings = WarningSet()
    if preset is ToolPreset.BROAD_WRITE:
        warnings.broad_write = True
    if preset is ToolPreset.FULL_ACCESS:
        warnings.full_access = True
    if preset is ToolPreset.CUSTOM:
        validation = validate_custom_tools(allowlist, catalog)
        warnings.unknown_custom_tools = validation.unknown_tools
    return warnings
