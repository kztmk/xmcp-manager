from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION_PATH = ROOT / "src/xmcp_manager/xmcp/VENDORED_XMCP_REVISION"
CATALOG_PATH = ROOT / "src/xmcp_manager/resources/tool_catalog.json"


def main() -> int:
    revision = REVISION_PATH.read_text(encoding="utf-8").strip()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_revision = catalog.get("xmcpRevision")
    if catalog_revision != revision:
        raise SystemExit(
            f"Tool catalog xmcpRevision {catalog_revision!r} does not match {revision!r}."
        )
    if not catalog.get("tools"):
        raise SystemExit("Tool catalog has no tools.")
    print(f"Tool catalog revision OK: {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
