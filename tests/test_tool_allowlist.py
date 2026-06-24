from xmcp_manager.models import RiskLevel, ToolCatalog, ToolDefinition, ToolPreset
from xmcp_manager.tool_allowlist import generate_allowlist, requires_warning, validate_custom_tools


def _catalog() -> ToolCatalog:
    return ToolCatalog(
        version=1,
        source="test",
        generated_at="2026-06-24T00:00:00Z",
        xmcp_revision="x",
        tools=[
            ToolDefinition("getUsersMe", "Profile", "profile", RiskLevel.READ),
            ToolDefinition("createPosts", "Posts", "post", RiskLevel.WRITE),
            ToolDefinition("deletePosts", "Posts", "post", RiskLevel.DESTRUCTIVE),
            ToolDefinition("mysteryTool", "Other", "other", RiskLevel.UNKNOWN),
        ],
    )


def test_read_only_allowlist_only_includes_read_tools() -> None:
    result = generate_allowlist(ToolPreset.READ_ONLY, [], _catalog())

    assert result.tools == ["getUsersMe"]
    assert result.env_value == "getUsersMe"


def test_broad_write_excludes_unknown_tools() -> None:
    result = generate_allowlist(ToolPreset.BROAD_WRITE, [], _catalog())

    assert "getUsersMe" in result.tools
    assert "createPosts" in result.tools
    assert "deletePosts" in result.tools
    assert "mysteryTool" not in result.tools


def test_custom_invalid_and_unknown_tools() -> None:
    validation = validate_custom_tools(["mysteryTool", "missingTool"], _catalog())
    warnings = requires_warning(ToolPreset.CUSTOM, ["mysteryTool"], _catalog())

    assert validation.ok is False
    assert validation.invalid_tools == ["missingTool"]
    assert validation.unknown_tools == ["mysteryTool"]
    assert warnings.unknown_custom_tools == ["mysteryTool"]
