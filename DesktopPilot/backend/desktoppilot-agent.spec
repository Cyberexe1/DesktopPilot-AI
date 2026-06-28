# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the DesktopPilot local agent.
Build:  pyinstaller desktoppilot-agent.spec --noconfirm
Output: dist/desktoppilot-agent/desktoppilot-agent.exe (+ supporting files)
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

# Local packages are imported lazily inside route handlers, so PyInstaller's
# static analysis misses them. Force-collect every submodule.
for pkg in ["controllers", "ai", "voice", "automation", "database", "indexer"]:
    hiddenimports += collect_submodules(pkg)

# Third-party packages that ship data/binaries or use dynamic imports.
# NOTE: faster_whisper/openwakeword/torch are intentionally NOT collected —
# transcription and wake-word run elsewhere; bundling torch would add ~2GB.
for pkg in ["pyttsx3", "comtypes", "boto3", "botocore"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Web server internals that are imported by string name.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += ["anyio", "click", "h11", "websockets", "multipart",
                  "win32timezone", "win32com", "win32com.client"]

a = Analysis(
    ["run_agent.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pytest",
        # Heavy ML stacks not used by the bundled agent (cloud handles AI):
        "torch", "torchaudio", "torchvision",
        "faster_whisper", "ctranslate2", "openwakeword",
        "transformers", "onnxruntime", "av",
        "scipy", "pandas", "pyarrow", "sympy", "sqlalchemy",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="desktoppilot-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="desktoppilot-agent",
)
