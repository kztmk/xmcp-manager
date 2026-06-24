# XMCP Manager

XMCP Manager is a desktop integration context for operating X through MCP clients by managing a local xmcp MCP server and its account credentials.

## Language

**XMCP Manager**:
A desktop GUI application that manages X account credentials, starts and stops the local xmcp MCP server, and updates MCP client configuration.
_Avoid_: XMCP app, xmcp GUI, setup script

**xmcp**:
An embedded external MCP server component that exposes X API operations to MCP clients.
_Avoid_: owned server, XMCP Manager backend

**X Account**:
A user account on X that owns or accesses a Developer Portal app whose API credentials are used for authentication.
_Avoid_: developer app, credential profile

**Account Metadata**:
Non-secret local information about an X Account, such as its handle, display name, or last-used timestamp.
_Avoid_: account credentials, API keys

**API Credentials**:
Secret authentication values issued for an X Developer App and used to authorize X API access for an X Account.
_Avoid_: account metadata, account name

**Tool Allowlist**:
A per-account set of xmcp tool names that XMCP Manager exposes to MCP clients through the xmcp server startup environment.
_Avoid_: permission, X app permission

**Server State**:
The user-visible lifecycle state of the managed xmcp process: stopped, starting, waiting for authentication, connectable, or error.
_Avoid_: process flag, running boolean

**MCP Client**:
A desktop application that connects to the local xmcp MCP endpoint, such as Claude Desktop or Codex Desktop.
_Avoid_: Claude-only client, server
