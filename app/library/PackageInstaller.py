import importlib
import importlib.metadata
import logging
import os
import subprocess
import sys
from pathlib import Path

import httpx

LOG = logging.getLogger("package_installer")


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int("".join(filter(str.isdigit, part)) or "0") for part in v.strip().split("."))


class Packages:
    def __init__(self, env: str | None, file: str | None, upgrade: bool = False):
        from_env = env.split() if env else []
        from_file = []

        if file:
            file = Path(file)
            if file.exists() and os.access(str(file), os.R_OK):
                with open(file) as f:
                    from_file: list[str] = [pkg.strip() for pkg in f if pkg.strip()]

        self.packages: list[str] = list(set(from_env + from_file))
        self.upgrade = bool(upgrade)

    def has_packages(self) -> bool:
        return len(self.packages) > 0

    def allow_upgrade(self) -> bool:
        return self.upgrade


class PackageInstaller:
    user_site: Path | None = None

    def __init__(self):
        if base_dir := os.environ.get("YTP_CONFIG_PATH"):
            base_dir = Path(base_dir)
            self.user_site = base_dir / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
            self.user_site.mkdir(parents=True, exist_ok=True)

            if str(self.user_site) not in sys.path:
                sys.path.insert(0, str(self.user_site))

    def action(self, pkg: str, upgrade: bool = False):
        current_version = self._get_installed_version(pkg)

        if upgrade and current_version:
            latest_version = self._get_latest_version(pkg)
            if latest_version and parse_version(current_version) >= parse_version(latest_version):
                LOG.info(f"'{pkg}' is already the latest version ({current_version}). Skipping upgrade.")
                return

        if current_version:
            LOG.info(f"'{pkg}' is already installed (version: {current_version}). Proceeding with upgrade...")
        else:
            LOG.info(f"'{pkg}' is not installed. Installing...")

        self._install_pkg(pkg)

    def _get_installed_version(self, pkg: str) -> str | None:
        try:
            return importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            return None

    def _get_latest_version(self, pkg: str) -> str | None:
        url = f"https://pypi.org/pypi/{pkg}/json"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                if 200 == resp.status_code:
                    return resp.json()["info"]["version"]
                LOG.warning(f"Failed to fetch '{pkg}' info: HTTP {resp.status_code}")
        except Exception as e:
            LOG.warning(f"Error while querying PyPI for '{pkg}': {e}")
        return None

    def _install_pkg(self, pkg: str):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--disable-pip-version-check",
                "--target",
                str(self.user_site),
                "--no-warn-script-location",
                pkg,
            ],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    def check(self, pkgs: Packages):
        """
        Checks for user supplied pip packages and installs them if they are not already installed.

        Args:
            pkgs (GetPackages): the class with packages and their settings.

        """
        if not pkgs.has_packages() or not self.user_site:
            return

        LOG.info(f"Checking for user pip packages: {', '.join(pkgs.packages)}")
        for package in pkgs.packages:
            try:
                self.action(package, upgrade=pkgs.allow_upgrade())
            except Exception as e:
                LOG.error(f"Failed to install or upgrade package '{package}'. Error message: {e!s}")
                LOG.exception(e)
