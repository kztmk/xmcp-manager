from __future__ import annotations

import argparse
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = data["project"]["version"]
    if not isinstance(version, str):
        raise SystemExit("pyproject.toml project.version must be a string.")
    return version


def _msix_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) > 4 or not all(part.isdigit() for part in parts):
        raise SystemExit(f"MSIX version must be numeric dot version, got {version!r}.")
    return ".".join([*parts, *(["0"] * (4 - len(parts)))])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", default="dist/XMCP Manager")
    parser.add_argument("--manifest", default="packaging/windows/AppxManifest.xml")
    parser.add_argument("--output-dir", default="build/msix")
    parser.add_argument("--publisher", default="CN=XMCP Manager")
    args = parser.parse_args()

    dist_dir = ROOT / args.dist_dir
    output_dir = ROOT / args.output_dir
    if not dist_dir.exists():
        raise SystemExit(f"PyInstaller dist directory not found: {dist_dir}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(dist_dir, output_dir)

    manifest = (ROOT / args.manifest).read_text(encoding="utf-8")
    manifest = manifest.replace("__VERSION__", _msix_version(_project_version()))
    manifest = manifest.replace("__PUBLISHER__", args.publisher)
    (output_dir / "AppxManifest.xml").write_text(manifest, encoding="utf-8")

    assets_dir = output_dir / "Assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    print(f"Prepared MSIX layout at {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
