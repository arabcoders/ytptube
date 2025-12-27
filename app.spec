import importlib.metadata
import os
import re
import sys
import tomllib

block_cipher = None

MANUAL_MAP = {
    "bgutil_ytdlp_pot_provider": ["yt_dlp_plugins"],
    "python-dotenv": ["dotenv"],
}


def top_level_modules(dist_name: str) -> list[str]:
    manual: list[str] | None = MANUAL_MAP.get(dist_name) or MANUAL_MAP.get(dist_name.replace("-", "_"))
    if manual:
        return manual

    try:
        dist = importlib.metadata.distribution(dist_name)

        top_level: list[str] = []
        for f in dist.files or []:
            if f.name == "top_level.txt":
                txt = (dist.locate_file(f)).read_text().splitlines()
                top_level.extend([line.strip() for line in txt if line.strip()])
                break

        if not top_level:
            for f in dist.files or []:
                if f.parent == "" and f.suffix == "" and "." not in f.name:
                    top_level.append(f.name)  # noqa: PERF401

        if top_level:
            return sorted(set(top_level))
    except Exception:
        pass

    return [dist_name.replace("-", "_")]


def parse_pyproject(path: str = "pyproject.toml") -> set[str]:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    reqs = set(data["project"]["dependencies"])
    for extra in data["project"].get("optional-dependencies", {}).values():
        reqs.update(extra)

    return {re.split(r"[ ;<>=]", r, 1)[0] for r in reqs}  # noqa: B034


dist_names = parse_pyproject()
hidden: list[str] = []

for dist in dist_names:
    if sys.platform != "win32" and dist in ("python-magic-bin", "tzdata"):
        continue
    if sys.platform == "win32" and dist == "python-magic":
        continue
    hidden.extend(top_level_modules(dist))

hidden += [
    "engineio.async_drivers.aiohttp",
    "socketio.async_drivers.aiohttp",
    "socketio",  # python-socketio top-level
    "engineio",
    "aiohttp",
    "dotenv",
    "app",
]

hidden = sorted(set(hidden))

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
    excludes=[],  # do NOT exclude libstdc++.so.6
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # type: ignore # noqa: F821

exe = EXE(  # noqa: F821 # type: ignore
    pyz,
    a.scripts,
    name="YTPTube",
    debug=False,
    strip=False,
    console=True,
    icon="ui/public/favicon.ico",
    exclude_binaries=True,
)

coll = COLLECT(  # noqa: F821 # type: ignore
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="YTPTube",
)
