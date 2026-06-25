# Real-device Smoke Checklist

Use this checklist before merging `develop` into `main`. X API calls are metered, so the X API live check is separate and optional unless a release explicitly requires it.

## Test matrix

Record each run with OS version, app source, commit SHA, and MCP client versions.

| Target | Required before `develop -> main` | Notes |
|---|---:|---|
| macOS app | Yes | Use local `.app` or signed release candidate DMG. |
| Windows app | Yes for Windows-facing changes | Use MSIX release candidate when packaging is affected. |
| Claude Desktop | Yes | Verify config status and manual snippet fallback. |
| Codex Desktop | Yes | Verify config status and manual snippet fallback. |
| X API live operation | Manual only | Run only with explicit approval because X API usage is metered. |

## Common app checks

- [ ] App launches without terminal-only errors.
- [ ] Window title is `XMCP Manager`.
- [ ] Account list renders when no accounts exist.
- [ ] Add account creates a new selectable account.
- [ ] Edit account handle and display name, then restart app and confirm they persist.
- [ ] Duplicate handle is rejected.
- [ ] Delete account removes metadata and warns if credential deletion fails.
- [ ] API Credentials form never re-displays saved secret values.
- [ ] Empty credential fields keep existing values during update.
- [ ] Credential status changes from `missing` to `ok` after valid save.
- [ ] Invalid or inaccessible credentials are visible as status, not silent failure.

## Tool Allowlist checks

- [ ] `read_only` preview allows only read-risk tools.
- [ ] `broad_write` preview excludes unknown-risk tools and shows a warning.
- [ ] `full_access` preview states that `X_API_TOOL_ALLOWLIST` is not set.
- [ ] `custom` accepts newline-separated tools.
- [ ] `custom` rejects invalid tool names.
- [ ] `custom` warns for unknown-risk tools.
- [ ] Saved preset and custom allowlist persist after app restart.

## MCP client config checks

- [ ] Clients tab shows endpoint URL.
- [ ] Claude Desktop status shows config path, current URL, match status, or parse error.
- [ ] Codex Desktop status shows config path, current URL, match status, or parse error.
- [ ] Manual snippets are visible for both clients.
- [ ] Selecting no client and updating shows a warning.
- [ ] Updating Claude Desktop preserves unrelated `mcpServers` entries.
- [ ] Updating Codex Desktop preserves unrelated TOML settings.
- [ ] Existing different `xmcp` URL prompts before overwrite.
- [ ] Re-confirmation is not shown again while the existing URL remains unchanged.
- [ ] Parse error path does not overwrite the file and shows manual snippet.
- [ ] Backup folder button opens the backup directory for the selected client.

## Server startup checks

- [ ] Starting without an account shows a warning.
- [ ] Starting with missing credentials is blocked.
- [ ] Starting with invalid custom allowlist is blocked.
- [ ] Starting with `broad_write` prompts until app-wide acceptance is saved.
- [ ] Starting with `full_access` prompts until app-wide acceptance is saved.
- [ ] Starting server updates `lastUsedAt`.
- [ ] Server state moves through `starting`.
- [ ] OAuth-related output changes state to `waiting_auth`.
- [ ] Connectable server changes state to `connectable`.
- [ ] Stop server changes state to `stopped`.
- [ ] Logs shown in the UI redact secret-like values.
- [ ] Port conflict or unmanaged server at the endpoint is shown as a blocking warning.

## Settings and Store validation checks

- [ ] Settings tab shows MCP endpoint and OAuth callback URI.
- [ ] Settings tab shows Store build state.
- [ ] Store validation can be run manually.
- [ ] Validation result records app version and validation timestamp.
- [ ] User data writable result is shown.
- [ ] Credential store available result is shown.
- [ ] Loopback available result is shown.
- [ ] Claude Desktop external config writable result is shown.
- [ ] Codex Desktop external config writable result is shown.
- [ ] Validation result persists after app restart.

## macOS checks

- [ ] Launch from source with `python -m xmcp_manager.main`.
- [ ] Launch PyInstaller app from `dist/XMCP Manager.app`.
- [ ] App Settings are created under the OS user data directory.
- [ ] Keychain save/read/delete flow works for credentials.
- [ ] Claude Desktop config path resolves under `~/Library/Application Support/Claude/`.
- [ ] Codex Desktop config path resolves under `~/.codex/config.toml`.
- [ ] If testing a signed DMG, app opens after install and notarization does not block launch.

## Windows / MSIX checks

- [ ] MSIX installs successfully.
- [ ] Installed app launches from Start menu.
- [ ] Settings tab Store validation runs in the installed app.
- [ ] Windows Credential Manager save/read/delete flow works.
- [ ] User data write succeeds.
- [ ] Loopback validation succeeds for `127.0.0.1`.
- [ ] Claude Desktop config write behavior is correct or manual snippet fallback is shown.
- [ ] Codex Desktop config write behavior is correct or manual snippet fallback is shown.
- [ ] `xmcp` server can bind the MCP endpoint.
- [ ] OAuth callback listener can bind the callback endpoint.
- [ ] Windows App Certification Kit / Store validation equivalent has no blocking failures.

## X API live check

Run this only when explicitly approved because X API usage is metered.

- [ ] Use a dedicated low-risk X account and Developer App.
- [ ] Confirm X Developer App callback URL matches the app callback URI.
- [ ] Save API Key, API Key Secret, and Bearer Token.
- [ ] Use `read_only` preset first.
- [ ] Start server and complete OAuth consent.
- [ ] Confirm selected MCP client can call a read-only tool such as authenticated user lookup.
- [ ] If write testing is required, switch to a dedicated test account and perform only one minimal post/create operation.
- [ ] Clean up any test post or generated content.
- [ ] Stop server after the test.

## Result template

```text
Date:
Tester:
Commit:
OS:
App source:
Claude Desktop version:
Codex Desktop version:
Store build:
X API live check: not run / passed / failed

Pass:
Fail:
Notes:
```
