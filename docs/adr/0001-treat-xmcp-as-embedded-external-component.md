# Treat xmcp as an embedded external component

XMCP Manager embeds `xmcp/server.py` for distribution and process management, but does not treat xmcp as project-owned server code. This keeps XMCP Manager focused on account metadata, credential storage, process lifecycle, tool allowlist configuration, and MCP client integration while preserving a clear boundary for upstream xmcp behavior.
