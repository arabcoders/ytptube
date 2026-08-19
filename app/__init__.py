import os
import sys
from pathlib import Path


def _add_package_paths() -> None:
    paths: list[Path] = []
    if value := os.environ.get("YTP_PYTHON_PATH"):
        paths.extend(path for item in value.split(os.pathsep) if (path := Path(item).expanduser()).is_dir())

    if base_dir := os.environ.get("YTP_CONFIG_PATH"):
        user_site = Path(base_dir) / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
        if not user_site.exists():
            user_site.mkdir(parents=True, exist_ok=True)
        if user_site.is_dir():
            paths.append(user_site)

    for path in reversed(paths):
        value = str(path)
        if value in sys.path:
            sys.path.remove(value)
        sys.path.insert(0, value)


_add_package_paths()
