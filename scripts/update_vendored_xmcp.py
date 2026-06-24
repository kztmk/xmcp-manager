from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "src/xmcp_manager/xmcp/server.py"
REVISION_PATH = ROOT / "src/xmcp_manager/xmcp/VENDORED_XMCP_REVISION"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise SystemExit("--revision must be a full 40-character lowercase commit SHA.")
    url = f"https://raw.githubusercontent.com/xdevplatform/xmcp/{args.revision}/server.py"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    SERVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    SERVER_PATH.write_text(response.text, encoding="utf-8")
    REVISION_PATH.write_text(args.revision + "\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_tool_catalog.py"),
            "--revision",
            args.revision,
        ],
        check=True,
        cwd=str(ROOT),
    )
    print(f"Updated vendored xmcp to {args.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
