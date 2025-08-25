import os
import platform
import tomllib

block_cipher = None

machine = platform.machine().lower()

with open("./uv.lock", "rb") as f:
    lock = tomllib.load(f)

hidden = [
    *{pkg["name"] for pkg in lock.get("package", [])},
    "aiohttp",
    "socketio",
    "engineio",
    "engineio.async_drivers.aiohttp",
    "socketio.async_drivers.aiohttp",
    "app",
]

hidden = [f.replace("-", "_") for f in hidden]

a = Analysis(  # noqa: F821 # type: ignore
    ["app/local.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ("ui/exported", "ui/exported"),
        ("app/", "app/"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["libstdc++.so.6"],
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
    console=True,
    icon="ui/public/favicon.ico",
    onefile=True,
)
