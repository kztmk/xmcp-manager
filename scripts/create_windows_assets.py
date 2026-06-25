from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _write_png(path: Path, width: int, height: int) -> None:
    # Simple solid-color PNG writer to avoid committing binary placeholder assets.
    pixel = bytes((24, 96, 128, 255))
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(raw, level=9)),
            _chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="build/msix/Assets")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    _write_png(output_dir / "Square150x150Logo.png", 150, 150)
    _write_png(output_dir / "Square44x44Logo.png", 44, 44)
    _write_png(output_dir / "StoreLogo.png", 50, 50)
    print(f"Wrote Windows assets to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
