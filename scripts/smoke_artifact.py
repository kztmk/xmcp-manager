from __future__ import annotations

import argparse
from pathlib import Path


def _require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Required artifact path is missing: {path}")


def _require_one(candidates: list[Path]) -> None:
    if not any(path.exists() for path in candidates):
        joined = "\n".join(str(path) for path in candidates)
        raise SystemExit(f"None of the required artifact paths exist:\n{joined}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    parser.add_argument("--platform", choices=["macos", "windows"], required=True)
    args = parser.parse_args()
    artifact = Path(args.artifact)
    _require(artifact)
    if args.platform == "macos":
        _require(artifact / "Contents/MacOS/XMCP Manager")
        resource_roots = [
            artifact / "Contents/Resources",
            artifact / "Contents/Resources/_internal",
        ]
    else:
        _require(artifact / "XMCP Manager.exe")
        resource_roots = [
            artifact,
            artifact / "_internal",
        ]
    _require_one([root / "xmcp_manager/resources/tool_catalog.json" for root in resource_roots])
    _require_one([root / "xmcp_manager/xmcp/server.py" for root in resource_roots])
    print(f"Artifact smoke check passed: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
