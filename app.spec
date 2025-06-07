import json
import os
import platform
import sys

block_cipher = None

# Detect OS and architecture to include the correct GTK/WebKit libs
machine = platform.machine().lower()
binaries = []
if sys.platform.startswith("linux"):
    if machine in ("x86_64", "amd64"):
        libdir = "/usr/lib/x86_64-linux-gnu"
    elif machine in ("aarch64", "arm64"):
        libdir = "/usr/lib/aarch64-linux-gnu"
    else:
        libdir = "/usr/lib"
    binaries = [
        (os.path.join(libdir, "libwebkit2gtk-4.1.so.0"), "."),
        (os.path.join(libdir, "libjavascriptcoregtk-4.1.so.0"), "."),
    ]
elif sys.platform == "darwin":
    binaries = [
        ("/Library/Frameworks/WebKit.framework/Versions/Current/WebKit", "."),
    ]
elif sys.platform.startswith("win"):
    # Windows DLLs go here (example paths)
    binaries = [("C:\\\\path\\\\to\\\\WebKit2.dll", ".")]

# pull in all your Pipfile.lock defaults as hidden-imports:
with open("Pipfile.lock") as f:
    lock = json.load(f)

hidden = [
    *list(lock.get("default", {}).keys()),
    "aiohttp",
    "socketio",
    "engineio",
    "engineio.async_drivers.aiohttp",
    "socketio.async_drivers.aiohttp",
]

hidden = [f.replace("-", "_") for f in hidden]

a = Analysis(
    ["app/native.py"],  # your entrypoint
    pathex=["."],  # make sure PyInstaller can find your code
    binaries=binaries,
    datas=[
        ("ui/exported", "ui/exported"),
        ("app/migrations", "migrations"),
        ("app/library/presets.json", "library"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="YTPTube",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    onefile=True,  # ← this makes it a single-file bundle
)
