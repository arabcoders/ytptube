#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from library.PackageInstaller import PackageInstaller, Packages

LOG: logging.Logger = logging.getLogger("upgrader")

if base_dir := os.environ.get("YTP_CONFIG_PATH"):
    base_dir = Path(base_dir)
    user_site: Path = base_dir / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"

    if not user_site.exists():
        user_site.mkdir(parents=True, exist_ok=True)

    if user_site.is_dir() and str(user_site) not in sys.path:
        sys.path.insert(0, str(user_site))


class Upgrader:
    def __init__(self):
        config_path: Path = Path(__file__).parent.parent / "var" / "config"
        if env_path := os.environ.get("YTP_CONFIG_PATH", None):
            config_path = Path(env_path)
        else:
            os.environ.update({"YTP_CONFIG_PATH": str(config_path)})

        if config_path.exists():
            envFile: Path = config_path / ".env"
            if envFile.exists():
                LOG.debug(f"loading environment variables from '{envFile}'.")
                load_dotenv(str(envFile))
        else:
            LOG.error(f"config path '{config_path}' doesn't exists.")

        pkg_installer = PackageInstaller()

        ytdlp_auto_update: bool = os.environ.get("YTP_YTDLP_AUTO_UPDATE", "true").strip().lower() == "true"
        ytdlp_version: str | None = os.environ.get("YTP_YTDLP_VERSION", "").strip() or None

        if ytdlp_auto_update:
            try:
                LOG.info("Checking for newer versions of 'yt-dlp' package.")
                pkg_name = "yt_dlp"
                if ytdlp_version:
                    LOG.info(f"Using specified version '{ytdlp_version}' for '{pkg_name}'.")
                    pkg_name += f"=={ytdlp_version}"

                pkg_installer.action(pkg=pkg_name, upgrade=True)

                from yt_dlp.version import __version__ as YTDLP_VERSION

                LOG.info(f"yt-dlp version is '{YTDLP_VERSION}' ")
            except Exception as e:
                LOG.exception(e)
                LOG.error(f"Failed to check/upgrade for yt-dlp package. '{e!s}'.")

        try:
            pkg_installer.check(
                Packages(
                    env=os.environ.get("YTP_PIP_PACKAGES", None),
                    file=str(Path(config_path, "pip.txt")),
                    upgrade=not bool(os.environ.get("YTP_PIP_IGNORE_UPDATES", None)),
                )
            )
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Failed to check for packages. '{e!s}'.")


if __name__ == "__main__":
    try:
        import coloredlogs

        coloredlogs.install(
            level=logging.INFO, fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s", datefmt="%H:%M:%S"
        )
    except ImportError:
        logging.basicConfig(level=logging.DEBUG)

    Upgrader()
