import importlib
import logging
import os
import subprocess
import sys
from pathlib import Path

LOG = logging.getLogger("package_installer")


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
    """
    This class is responsible for installing and upgrading pip packages.
    """

    def action(self, pkg: str, upgrade: bool = False):
        try:
            importlib.import_module(pkg)
            if upgrade is False:
                LOG.info(f"'{pkg}' is already installed. Skipping upgrades. as requested.")
                return

            LOG.info(f"'{pkg}' is already installed. Checking for upgrades...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pkg], check=True)  # noqa: S603
        except ImportError:
            LOG.info(f"'{pkg}' is not installed. Installing...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)  # noqa: S603

    def check(self, pkgs: Packages):
        """
        Checks for user supplied pip packages and installs them if they are not already installed.

        Args:
            pkgs (GetPackages): the class with packages and their settings.

        """
        if not pkgs.has_packages():
            return

        LOG.info(f"Checking for user pip packages: {', '.join(pkgs.packages)}")
        for package in pkgs.packages:
            try:
                self.action(package, upgrade=pkgs.allow_upgrade())
            except Exception as e:
                LOG.error(f"Failed to install or upgrade package '{package}'. Error message: {e!s}")
                LOG.exception(e)
