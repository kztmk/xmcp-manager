# Support multiple MCP clients

XMCP Manager treats Claude Desktop and Codex Desktop as MCP clients that can connect to the same local xmcp HTTP endpoint. Client-specific config writers update only the managed xmcp server entry for each client, while the endpoint host and port remain app-wide settings shared across clients.
