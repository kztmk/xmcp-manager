# Switch accounts by restarting xmcp

XMCP Manager switches X accounts by stopping the current xmcp process and starting a new one with the selected account's credentials and tool allowlist. This accepts a short MCP client disconnection in exchange for a simple boundary that avoids modifying xmcp or multiplexing multiple X identities inside one server process.
