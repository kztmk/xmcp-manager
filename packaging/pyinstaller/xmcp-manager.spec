# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


block_cipher = None
name = "XMCP Manager"
root = Path(SPECPATH).parents[1]

hiddenimports = []
datas = collect_data_files("xmcp_manager") + [
    (str(root / "src/xmcp_manager/xmcp/server.py"), "xmcp_manager/xmcp"),
    (
        str(root / "src/xmcp_manager/xmcp/VENDORED_XMCP_REVISION"),
        "xmcp_manager/xmcp",
    ),
]

a = Analysis(
    [str(root / "src/xmcp_manager/main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "PyQt5",
        "PySide6",
        "black",
        "matplotlib",
        "nbformat",
        "pytest",
        "sphinx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=name,
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{name}.app",
        icon=None,
        bundle_identifier="com.imakita3gyo.xmcpmanager",
        info_plist={
            "CFBundleName": name,
            "CFBundleDisplayName": name,
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
