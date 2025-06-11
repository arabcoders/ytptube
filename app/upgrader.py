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

LOG = logging.getLogger("upgrader")


class Upgrader:
    def __init__(self):
        config_path: Path = Path(__file__).parent.parent / "var" / "config"
        if env_path := os.environ.get("YTP_CONFIG_PATH", None):
            config_path = Path(env_path)

        if config_path.exists():
            envFile: Path = config_path / ".env"
            if envFile.exists():
                LOG.debug(f"loading environment variables from '{envFile}'.")
                load_dotenv(str(envFile))
        else:
            LOG.error(f"config path '{config_path}' doesn't exists.")

        pkg_installer = PackageInstaller()

        ytdlp_auto_update: bool = os.environ.get("YTP_YTDLP_AUTO_UPDATE", "true").strip().lower() == "true"

        if ytdlp_auto_update:
            try:
                LOG.info("Checking for newer versions of 'yt-dlp' package.")
                pkg_installer.action(pkg="yt_dlp", upgrade=True)

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
                    upgrade=not bool(os.environ.get("YTP_PIP_IGNORE_UPDATES", False)),
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
