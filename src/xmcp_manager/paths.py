from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "XMCP Manager"
APP_AUTHOR = "XMCP Manager"


def get_user_data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_settings_path() -> Path:
    return get_user_data_dir() / "app_settings.json"


def get_accounts_path() -> Path:
    return get_user_data_dir() / "accounts.json"


def get_user_tool_catalog_path() -> Path:
    return get_user_data_dir() / "tool_catalog.json"


def get_backup_dir(client_id: str) -> Path:
    path = get_user_data_dir() / "backups" / client_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_bundled_resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = [
        base / "resources" / name,
        Path(__file__).resolve().parent / "resources" / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def get_vendored_xmcp_dir() -> Path:
    return Path(__file__).resolve().parent / "xmcp"


def open_folder(path: Path) -> None:
    folder = path if path.is_dir() else path.parent
    if sys.platform == "darwin":
        subprocess.run(["open", str(folder)], check=False)
    elif os.name == "nt":
        os.startfile(str(folder))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(folder)], check=False)
