# Release Operations

## Branch flow

- Feature work lands in `feature/*`.
- Verified feature branches merge into `develop`.
- After real-device verification using `docs/smoke-checklist.md`, `develop` merges into `main`.
- Release candidate builds are produced from the `release` branch.
- Draft GitHub releases are produced from `v*` tags after the tag matches `pyproject.toml`.

## Required GitHub Secrets

macOS release candidate builds require:

- `APPLE_CERTIFICATE_BASE64`: base64 encoded Developer ID Application `.p12`
- `APPLE_CERTIFICATE_PASSWORD`: password for the `.p12`
- `APPLE_DEVELOPER_ID_APPLICATION`: codesign identity name
- `APPLE_ID`: Apple ID used for notarization
- `APPLE_TEAM_ID`: Apple Developer Team ID
- `APPLE_APP_SPECIFIC_PASSWORD`: app-specific password for notarization

Windows MSIX builds optionally use:

- `XMCP_MSIX_PUBLISHER`: Partner Center publisher string. Defaults to `CN=XMCP Manager` for unsigned candidate packaging.

Do not commit signing certificates, app-specific passwords, Partner Center credentials, or Store submission credentials to the repository.
