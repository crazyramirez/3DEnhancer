# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


PROJECT_ROOT = Path(SPECPATH)
IS_MACOS = sys.platform == "darwin"
ICON_FILE = PROJECT_ROOT / "assets" / ("app_icon.icns" if IS_MACOS else "app_icon.ico")

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(PROJECT_ROOT / "assets" / "app_icon.png"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "Cython",
        "IPython",
        "aiohttp",
        "cryptography",
        "fsspec",
        "lxml",
        "llvmlite",
        "matplotlib",
        "numba",
        "openpyxl",
        "pandas",
        "pyarrow",
        "pytest",
        "requests",
        "scipy",
        "tkinter",
        "trio",
        "websockets",
        "win32com",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="3D Enhancer",
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
    icon=str(ICON_FILE),
    version=(str(PROJECT_ROOT / "packaging" / "version_info.txt") if not IS_MACOS else None),
)

if IS_MACOS:
    app = BUNDLE(
        exe,
        name="3D Enhancer.app",
        icon=str(ICON_FILE),
        bundle_identifier="com.threedenhancer.app",
        info_plist={
            "CFBundleName": "3D Enhancer",
            "CFBundleDisplayName": "3D Enhancer",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
        },
    )
