from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected git tag, for example v1.2.3.")
    args = parser.parse_args()

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    package_version = (ROOT / "src/xmcp_manager/__init__.py").read_text(encoding="utf-8")
    expected_line = f'__version__ = "{project_version}"'
    if expected_line not in package_version:
        raise SystemExit(
            f"src/xmcp_manager/__init__.py does not match pyproject version {project_version}."
        )
    if args.tag:
        expected_tag = f"v{project_version}"
        if args.tag != expected_tag:
            raise SystemExit(f"Tag {args.tag} does not match project version {project_version}.")
    print(project_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
