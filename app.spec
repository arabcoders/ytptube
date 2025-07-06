import os
import platform
import sys
import tomllib

block_cipher = None

machine = platform.machine().lower()
binaries = []
if sys.platform.startswith("linux"):
    if machine in ("x86_64", "amd64"):
        libdir = "/usr/lib/x86_64-linux-gnu"
    elif machine in ("aarch64", "arm64"):
        libdir = "/usr/lib/aarch64-linux-gnu"
    else:
        libdir = "/usr/lib"
    binaries = []
elif sys.platform == "darwin":
    binaries = []
elif sys.platform.startswith("win"):
    # Windows DLLs
    binaries = []

with open("./uv.lock", "rb") as f:
    lock = tomllib.load(f)

hidden = [
    *{pkg["name"] for pkg in lock.get("package", [])},
    "aiohttp",
    "socketio",
    "engineio",
    "engineio.async_drivers.aiohttp",
    "socketio.async_drivers.aiohttp",
    "app"
]

hidden = [f.replace("-", "_") for f in hidden]

a = Analysis(  # noqa: F821 # type: ignore
    ["app/native.py"],
    pathex=[os.getcwd()],
    binaries=binaries,
    datas=[
        ("ui/exported", "ui/exported"),
        ("app/", "app/"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # type: ignore # noqa: F821

exe = EXE(  # type: ignore # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="YTPTube",
    debug=False,
    strip=False,
    upx=True,
    console=False, # Turn on to True if you want a console window for debugging.
    icon="ui/public/favicon.ico",
    onefile=True,
)
