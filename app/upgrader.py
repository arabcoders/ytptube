#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import logging
import os
from pathlib import Path

from library.PackageInstaller import PackageInstaller, Packages

LOG: logging.Logger = logging.getLogger("upgrader")


class Upgrader:
    def __init__(self):
        config_path: Path = Path(__file__).parent.parent / "var" / "config"
        if env_path := os.environ.get("YTP_CONFIG_PATH", None):
            config_path = Path(env_path)
        else:
            os.environ.update({"YTP_CONFIG_PATH": str(config_path)})

        if not config_path.exists():
            LOG.error("Config path '%s' does not exist.", config_path, extra={"config_path": str(config_path)})
            return

        envFile: Path = config_path / ".env"
        if envFile.exists():
            from dotenv import load_dotenv

            LOG.debug("Loading environment variables from '%s'.", envFile, extra={"env_file": str(envFile)})
            load_dotenv(str(envFile))

        user_site: Path = config_path / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
        user_site_ver: Path = user_site / ".version"

        from app.library.version import APP_COMMIT_SHA, APP_VERSION

        version: str = f"{APP_VERSION}-{APP_COMMIT_SHA[:8]}"

        if not user_site.exists():
            user_site.mkdir(parents=True, exist_ok=True)
            user_site_ver.write_text(version)

        if user_site.is_dir():
            if str(user_site) not in sys.path:
                sys.path.insert(0, str(user_site))

            if not user_site_ver.exists() or version != user_site_ver.read_text().strip():
                self.clean_up(user_site, user_site_ver, version)

        self.check(config_path, user_site)

    def clean_up(self, user_site: Path, user_site_ver: Path, app_version: str) -> None:
        LOG.info(
            "Cleaning up user site packages at '%s' for app version '%s'.",
            user_site,
            app_version,
            extra={"user_site": str(user_site), "app_version": app_version},
        )
        from app.library.Utils import delete_dir

        if not delete_dir(user_site):
            LOG.error("Failed to clean up user site packages at '%s'.", user_site, extra={"user_site": str(user_site)})
            return

        try:
            user_site.mkdir(parents=True, exist_ok=True)
            user_site_ver.write_text(app_version)
            LOG.info(
                "User site packages at '%s' are ready for app version '%s'.",
                user_site,
                app_version,
                extra={"user_site": str(user_site), "app_version": app_version},
            )
        except Exception as e:
            LOG.exception(
                "Failed to recreate user site packages at '%s'.",
                user_site,
                extra={"user_site": str(user_site), "app_version": app_version, "exception_type": type(e).__name__},
            )

    def check(self, config_path: Path, user_site: Path) -> None:
        pkg_installer = PackageInstaller(pkg_path=user_site)

        ytdlp_auto_update: bool = os.environ.get("YTP_YTDLP_AUTO_UPDATE", "true").strip().lower() == "true"
        ytdlp_version: str | None = os.environ.get("YTP_YTDLP_VERSION", "").strip() or None

        if ytdlp_auto_update:
            try:
                LOG.info("Checking for newer versions of 'yt-dlp' package.")
                pkg_name = "yt_dlp"
                if ytdlp_version:
                    LOG.info(
                        "Using requested version '%s' for package '%s'.",
                        ytdlp_version,
                        pkg_name,
                        extra={"package": pkg_name, "requested_version": ytdlp_version},
                    )
                    pkg_name += f"=={ytdlp_version}"

                pkg_installer.action(pkg=pkg_name, upgrade=True)

                from yt_dlp.version import __version__ as YTDLP_VERSION

                LOG.info(
                    "yt-dlp version is '%s'.", YTDLP_VERSION, extra={"package": "yt_dlp", "version": YTDLP_VERSION}
                )
            except Exception as e:
                LOG.exception(
                    "Failed to check or upgrade yt-dlp package.",
                    extra={"package": "yt_dlp", "requested_version": ytdlp_version, "exception_type": type(e).__name__},
                )

        try:
            pkg_installer.check(
                Packages(
                    env=os.environ.get("YTP_PIP_PACKAGES", None),
                    file=str(Path(config_path, "pip.txt")),
                    upgrade=not bool(os.environ.get("YTP_PIP_IGNORE_UPDATES", None)),
                )
            )
        except Exception as e:
            LOG.exception(
                "Failed to check configured pip packages.",
                extra={
                    "config_path": str(config_path),
                    "user_site": str(user_site),
                    "exception_type": type(e).__name__,
                },
            )


if __name__ == "__main__":
    try:
        import coloredlogs

        coloredlogs.install(
            level=logging.INFO, fmt="%(asctime)s [%(name)s] [%(levelname)-5.5s] %(message)s", datefmt="%H:%M:%S"
        )
    except ImportError:
        logging.basicConfig(level=logging.DEBUG)

    Upgrader()
