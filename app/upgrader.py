#!/usr/bin/env python3

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from library.PackageInstaller import PackageInstaller, Packages

LOG = logging.getLogger("upgrader")


class Upgrader:
    def __init__(self):
        import argparse

        parser = argparse.ArgumentParser(
            prog="upgrader.py",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description="Upgrade packages and run the application.",
            epilog="Example: upgrader.py --run",
        )

        parser.add_argument(
            "-r", "--run", action="store_true", help="Run the application after upgrading the packages."
        )

        args, _ = parser.parse_known_args()

        rootPath = str(Path(__file__).parent.parent.absolute())
        config_path = os.environ.get("YTP_CONFIG_PATH", None) or os.path.join(rootPath, "var", "config")
        if not Path(config_path).exists():
            LOG.error(f"config path '{config_path}' doesn't exists.")

        envFile = Path(config_path, ".env")
        if envFile.exists():
            LOG.debug(f"loading environment variables from '{envFile}'.")
            load_dotenv(str(envFile))

        pkg_installer = PackageInstaller()

        ytdlp_auto_update: bool = bool(os.environ.get("YTP_YTDLP_AUTO_UPDATE", False))

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

        if args.run:
            from main import Main

            Main().start()


if __name__ == "__main__":
    try:
        import coloredlogs

        logging.basicConfig(level=logging.DEBUG)
        coloredlogs.install(
            level=logging.INFO, fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s", datefmt="%H:%M:%S"
        )
    except ImportError:
        pass

    Upgrader()
