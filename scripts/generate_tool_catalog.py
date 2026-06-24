from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from xmcp_manager.tool_allowlist import (  # noqa: E402
    OPENAPI_URL,
    _catalog_to_dict,
    catalog_from_openapi_spec,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", default="src/xmcp_manager/resources/tool_catalog.json")
    args = parser.parse_args()
    response = httpx.get(OPENAPI_URL, timeout=30)
    response.raise_for_status()
    catalog = catalog_from_openapi_spec(response.json(), xmcp_revision=args.revision)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(_catalog_to_dict(catalog), f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {len(catalog.tools)} tools to {output}")
    unknown = [tool.name for tool in catalog.tools if tool.risk_level.value == "unknown"]
    if unknown:
        print(f"WARNING: {len(unknown)} tools are unknown/uncategorized.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
