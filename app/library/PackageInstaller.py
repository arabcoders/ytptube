import importlib
import logging
import os
import subprocess
import sys

from library.config import Config

LOG = logging.getLogger("package_installer")


class PackageInstaller:
    """
    This class is responsible for installing and upgrading pip packages.
    """

    def __init__(self, config: Config):
        self.config: Config = config

    def from_env(self):
        return self.config.pip_packages.split() if self.config.pip_packages else []

    def from_file(self, file_path):
        if not os.path.exists(file_path):
            return []

        if os.access(file_path, os.R_OK):
            with open(file_path) as f:
                return [pkg.strip() for pkg in f if pkg.strip()]
        else:
            LOG.error(f"Could not read pip packages from '{file_path}'.")
            return []

    def action(self, pkg: str):
        try:
            importlib.import_module(pkg)
            if self.config.pip_ignore_updates:
                LOG.info(f"'{pkg}' is already installed. Skipping upgrades. as requested.")
                return
            LOG.info(f"'{pkg}' is already installed. Checking for upgrades...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", pkg], check=True)  # noqa: S603
        except ImportError:
            LOG.info(f"'{pkg}' is not installed. Installing...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)  # noqa: S603

    def check(self):
        """
        Checks for user supplied pip packages and installs them if they are not already installed.
        """
        pip_file = os.path.join(self.config.config_path, "pip.txt")
        packages = list(set(self.from_env() + self.from_file(pip_file)))

        if not packages:
            return

        LOG.info(f"Checking for user pip packages: {', '.join(packages)}")
        for package in packages:
            try:
                self.action(package)
            except Exception as e:
                LOG.error(f"Failed to install or upgrade package '{package}'. Error message: {e!s}")
                LOG.exception(e)
